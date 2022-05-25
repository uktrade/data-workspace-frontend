import logging
import os

from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import messages
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView
from requests import HTTPError
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.forms import (
    SupportForm,
    TechnicalSupportForm,
    UserSatisfactionSurveyForm,
)
from dataworkspace.apps.core.models import (
    UserSatisfactionSurvey,
    NewsletterSubscription,
)
from dataworkspace.apps.core.storage import S3FileStorage
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    can_access_schema_table,
    get_dataflow_dag_status,
    get_dataflow_task_status,
    table_data,
    table_exists,
    view_exists,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.zendesk import create_support_request

logger = logging.getLogger("app")


def public_error_404_html_view(request, exception=None):
    return render(request, "errors/error_404.html", status=404)


def public_error_403_html_view(request, exception=None):
    default_template = "errors/error_403.html"
    if exception is None:
        return render(request, default_template, status=403)
    return render(
        request,
        getattr(exception, "template_name", default_template),
        getattr(exception, "template_context", {}),
        status=403,
    )


def public_error_403_csrf_html_view(request, reason=None):
    return render(request, "errors/error_403_csrf.html", status=403)


def public_error_403_tool_permission_denied_html_view(request):
    return render(request, "errors/error_403_tool_permission_denied.html", status=403)


def public_error_403_invalid_tool_user_html_view(request):
    return render(request, "errors/error_403_invalid_tool_user.html", status=403)


def public_error_500_html_view(request):
    message = request.GET.get("message", None)
    return render(request, "errors/error_500.html", {"message": message}, status=500)


def healthcheck_view(_):
    return HttpResponse("OK")


def about_page_view(request):
    return render(request, "about.html", {}, status=200)


class SupportView(FormView):
    form_class = SupportForm
    template_name = "core/support.html"

    ZENDESK_TAGS = {"data-request": "data_request"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx["ticket_id"] = self.kwargs.get("ticket_id")
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = self.request.user.email
        return initial

    def form_valid(self, form):
        cleaned = form.cleaned_data

        if cleaned["support_type"] == form.SupportTypes.NEW_DATASET:
            return HttpResponseRedirect(reverse("request_data:index"))

        if cleaned["support_type"] == form.SupportTypes.TECH_SUPPORT:
            return HttpResponseRedirect(
                f'{reverse("technical-support")}?email={cleaned["email"]}'
            )

        tag = self.ZENDESK_TAGS.get(self.request.GET.get("tag"))
        ticket_id = create_support_request(
            self.request.user, cleaned["email"], cleaned["message"], tag=tag
        )
        return HttpResponseRedirect(
            reverse("support-success", kwargs={"ticket_id": ticket_id})
        )


class NewsletterSubscriptionView(View):
    def get(self, request):
        subscribed = NewsletterSubscription.objects.filter(
            user=self.request.user, is_active=True
        ).exists()
        return render(
            request,
            "core/newsletter_subscription.html",
            context={
                "is_currently_subscribed": subscribed,
            },
        )

    def post(self, request):
        should_subscribe = request.POST.get("action") == "subscribe"
        subscription, created = NewsletterSubscription.objects.get_or_create(
            user=self.request.user
        )
        subscription.is_active = should_subscribe
        subscription.save()

        messages.success(
            request,
            "You have %s the newsletter"
            % ("subscribed to" if should_subscribe else "unsubscribed from"),
        )
        return HttpResponseRedirect(reverse("root"))


class UserSatisfactionSurveyView(FormView):
    form_class = UserSatisfactionSurveyForm
    template_name = "core/user-satisfaction-survey.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx["referer"] = self.request.META.get("HTTP_REFERER")
        return ctx

    def form_valid(self, form):
        cleaned = form.cleaned_data
        UserSatisfactionSurvey.objects.create(
            how_satisfied=cleaned["how_satisfied"],
            trying_to_do=",".join(cleaned["trying_to_do"]),
            improve_service=cleaned["improve_service"],
        )

        return HttpResponseRedirect(f'{reverse("feedback")}?success=1')


def table_data_view(request, database, schema, table):
    logger.info(
        "table_data_view attempt: %s %s %s %s",
        request.user.email,
        database,
        schema,
        table,
    )

    log_event(
        request.user,
        EventLog.TYPE_DATASET_TABLE_DATA_DOWNLOAD,
        extra={
            "path": request.get_full_path(),
            "database": database,
            "schema": schema,
            "table": table,
        },
    )

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    elif not can_access_schema_table(request.user, database, schema, table):
        return HttpResponseForbidden()
    elif not (
        view_exists(database, schema, table) or table_exists(database, schema, table)
    ):
        return HttpResponseNotFound()
    else:
        return table_data(request.user.email, database, schema, table)


class TechnicalSupportView(FormView):
    form_class = TechnicalSupportForm
    template_name = "core/technical_support.html"

    def get(self, request, *args, **kwargs):
        if "email" not in self.request.GET:
            return HttpResponseBadRequest("Expected an `email` parameter")
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = self.request.GET["email"]
        return initial

    def form_valid(self, form):
        cleaned = form.cleaned_data
        message = (
            f'What were you trying to do?\n{cleaned["what_were_you_doing"]}\n\n'
            f'What happened?\n{cleaned["what_happened"]}\n\n'
            f'What should have happened?\n{cleaned["what_should_have_happened"]}'
        )
        ticket_id = create_support_request(self.request.user, cleaned["email"], message)
        return HttpResponseRedirect(
            reverse("support-success", kwargs={"ticket_id": ticket_id})
        )


class ServeS3UploadedFileView(View):
    def get(self, request, *args, **kwargs):
        file_storage = S3FileStorage()
        path = request.GET.get("path")
        if path is None:
            return HttpResponseBadRequest("Expected a `path` parameter")

        if not path.startswith(file_storage.base_prefix):
            return HttpResponseNotFound()

        client = get_s3_client()
        try:
            file_object = client.get_object(Bucket=file_storage.bucket, Key=path)
        except ClientError as ex:
            try:
                return HttpResponse(
                    status=ex.response["ResponseMetadata"]["HTTPStatusCode"]
                )
            except KeyError:
                return HttpResponseServerError()

        response = StreamingHttpResponseWithoutDjangoDbConnection(
            file_object["Body"].iter_chunks(chunk_size=65536),
            content_type=file_object["ContentType"],
        )
        response[
            "Content-Disposition"
        ] = f'attachment; filename="{os.path.split(path)[-1].rpartition("!")[0]}"'
        response["Content-Length"] = file_object["ContentLength"]
        return response


class CreateTableDAGStatusView(View):
    """
    Check on the status of a DAG that has been run via the create table flow.

    Airflow 1 requires calling with the execution date which is not ideal. Once
    we have upgraded to Airflow 2 we can update this to call with the unique dag run id.

    Airflow 2 will also return more info, including the config we called the API with
    to trigger the DAG. Once we have this available we can then check if the file
    path in the response matches the s3 path prefix for the current user - as an extra
    step to check the current user actually created this dag run themselves.
    """

    def get(self, request, execution_date):
        config = settings.DATAFLOW_API_CONFIG
        try:
            return JsonResponse(
                get_dataflow_dag_status(
                    config["DATAFLOW_S3_IMPORT_DAG"], execution_date
                )
            )
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)


class CreateTableDAGTaskStatusView(View):
    def get(self, request, execution_date, task_id):
        config = settings.DATAFLOW_API_CONFIG
        try:
            return JsonResponse(
                {
                    "state": get_dataflow_task_status(
                        config["DATAFLOW_S3_IMPORT_DAG"], execution_date, task_id
                    )
                }
            )
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)


class RestoreTableDAGTaskStatusView(View):
    def get(self, request, execution_date, task_id):
        config = settings.DATAFLOW_API_CONFIG
        try:
            return JsonResponse(
                {
                    "state": get_dataflow_task_status(
                        config["DATAFLOW_RESTORE_TABLE_DAG"], execution_date, task_id
                    )
                }
            )
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)
