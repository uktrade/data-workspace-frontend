import json
import logging
import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import messages
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView
from requests import HTTPError

from dataworkspace.apps.applications.models import ApplicationInstance, VisualisationTemplate
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.forms import (
    AddDatasetRequestForm,
    ContactUsForm,
    CustomVisualisationReviewForm,
    NewsletterSubscriptionForm,
    SupportAnalysisDatasetForm,
    SupportForm,
    TechnicalSupportForm,
    UserSatisfactionSurveyForm,
)
from dataworkspace.apps.core.models import NewsletterSubscription, UserSatisfactionSurvey
from dataworkspace.apps.core.storage import S3FileStorage
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    can_access_schema_table,
    check_db,
    get_data_flow_import_pipeline_name,
    get_dataflow_dag_status,
    get_dataflow_task_status,
    is_last_days_remaining_notification_banner,
    table_data,
    table_exists,
    view_exists,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.notification_banner.models import NotificationBanner
from dataworkspace.zendesk import create_support_request

logger = logging.getLogger("app")


def public_error_404_html_view(request, exception=None):
    return render(request, "errors/error_404.html", status=404)


def public_error_403_html_view(request, exception=None):
    default_template = "errors/error_403.html"
    if exception is None:
        return render(
            request,
            default_template,
            context={"peer_ip": request.META.get("HTTP_X_FORWARDED_FOR")},
            status=403,
        )
    return render(
        request,
        getattr(exception, "template_name", default_template),
        getattr(exception, "template_context", {}),
        status=403,
    )


def public_error_403_visualisation_html_view(request, exception=None):
    default_template = "errors/error_403_visualisation.html"
    host_basename = request.GET.get("host")

    contact_email = None
    try:
        vis_template = VisualisationTemplate.objects.get(host_basename=host_basename)
    except VisualisationTemplate.DoesNotExist:
        pass
    else:
        catalogue_item = vis_template.visualisationcatalogueitem
        if catalogue_item.enquiries_contact is not None:
            contact_email = catalogue_item.enquiries_contact.email
        elif catalogue_item.information_asset_manager is not None:
            contact_email = catalogue_item.information_asset_manager.email

    if exception is None:
        return render(
            request,
            default_template,
            context={
                "peer_ip": request.META.get("HTTP_X_FORWARDED_FOR"),
                "contact_email": contact_email,
            },
            status=403,
        )
    return render(
        request,
        getattr(exception, "template_name", default_template),
        {**getattr(exception, "template_context", {}), "contact_email": contact_email},
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


def public_error_500_application_view(request):
    app_id = request.GET.get("application_id", "")
    spawner_instance_id = None
    if app_id != "":
        application = ApplicationInstance.objects.get(pk=app_id)
        spawner_instance_id = json.loads(application.spawner_application_instance_id or "{}")
        if application.application_template.include_in_dw_stats:
            log_event(
                request.user,
                EventLog.TYPE_USER_TOOL_FAILED,
                application,
                extra={
                    "tool": application.application_template.nice_name,
                    "started": application.spawner_created_at,
                    "failure_message": request.GET.get("failure_message", None),
                },
            )
    if (
        spawner_instance_id
        and spawner_instance_id.get("pipeline_id")
        and not spawner_instance_id.get("task_arn")
    ):
        build_log_url = (
            settings.GITLAB_URL_FOR_TOOLS
            + f"deployment/docker-ecr/-/pipelines/{spawner_instance_id.get('pipeline_id')}"
        )
        return render(
            request,
            "errors/error_500_visualisation_docker_build.html",
            {
                "message": request.GET.get("message", None),
                "build_log_url": build_log_url,
            },
            status=500,
        )
    else:
        return render(
            request,
            "errors/error_500.html",
            {"message": request.GET.get("message", None)},
            status=500,
        )


def healthcheck_view(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if check_db("default"):
        return HttpResponse("OK")
    return HttpResponseServerError("Database not available")


def about_page_view(request):
    return render(request, "about.html", {}, status=200)


def welcome_page_view(request):
    return render(request, "welcome.html", {}, status=200)


class SupportView(FormView):
    form_class = SupportForm
    template_name = "core/support.html"

    ZENDESK_TAGS = {
        "data-request": "data_request",
        "add-dataset-request": "add_dataset_request",
        "custom-visualisation-request": "custom_visualisation_request",
        "data-analysis-support-request": "data_analysis_support_request",
    }

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
        support_Type = cleaned["support_type"]
        if support_Type == form.SupportTypes.NEW_DATASET:
            return HttpResponseRedirect(
                f'{reverse("add-dataset-request")}?email={cleaned["email"]}'
            )
        elif support_Type == form.SupportTypes.TECH_SUPPORT:
            return HttpResponseRedirect(f'{reverse("technical-support")}?email={cleaned["email"]}')
        elif support_Type == form.SupportTypes.DATA_ANALYSIS_SUPPORT:
            return HttpResponseRedirect(
                f'{reverse("support-analysis-dataset")}?email={cleaned["email"]}'
            )
        elif support_Type == form.SupportTypes.VISUALISATION_REVIEW:
            return HttpResponseRedirect(
                f'{reverse("custom-visualisation-review")}?email={cleaned["email"]}'
            )
        tag = self.ZENDESK_TAGS.get(self.request.GET.get("tag"))
        ticket_id = create_support_request(
            self.request.user, cleaned["email"], cleaned["message"], tag=tag
        )
        return HttpResponseRedirect(
            f'{reverse("support-success", kwargs={"ticket_id": ticket_id})}'
        )


class SupportRequestView(SupportView):
    def get(self, request, *args, **kwargs):
        if "email" not in self.request.GET:
            return HttpResponseBadRequest("Expected an `email` parameter")
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        cleaned = form.cleaned_data
        tag = self.ZENDESK_TAGS.get(self.request.GET.get("tag"))
        ticket_id = create_support_request(
            self.request.user, cleaned["email"], cleaned["message"], tag=tag
        )
        add_dataset = isinstance(self, AddDatasetRequestView)
        data_analyst = isinstance(self, SupportAnalysisDatasetView)
        return HttpResponseRedirect(
            f'{reverse("support-success", kwargs={"ticket_id": ticket_id})}?add_dataset={add_dataset}&data_analyst={data_analyst}'  # pylint: disable=line-too-long
        )


class AddDatasetRequestView(SupportRequestView):
    form_class = AddDatasetRequestForm
    template_name = "core/add_dataset_request.html"


class CustomVisualisationReviewView(SupportRequestView):
    form_class = CustomVisualisationReviewForm
    template_name = "core/custom_visualisation_review.html"


class SupportAnalysisDatasetView(SupportRequestView):
    form_class = SupportAnalysisDatasetForm
    template_name = "core/support_dataset_analysis.html"


class TechnicalSupportView(SupportRequestView):
    form_class = TechnicalSupportForm
    template_name = "core/technical_support.html"

    def form_valid(self, form):
        cleaned = form.cleaned_data
        message = (
            f'What were you trying to do?\n{cleaned["what_were_you_doing"]}\n\n'
            f'What happened?\n{cleaned["what_happened"]}\n\n'
            f'What should have happened?\n{cleaned["what_should_have_happened"]}'
        )
        ticket_id = create_support_request(self.request.user, cleaned["email"], message)
        return HttpResponseRedirect(reverse("support-success", kwargs={"ticket_id": ticket_id}))


class NewsletterSubscriptionView(View):
    def _get_subscription_info(self, user):
        subscribed = False
        email = user.email

        try:
            subscription = NewsletterSubscription.objects.get(user=user)

            subscribed = subscription.is_active
            email = (
                subscription.email_address if subscription.is_active else self.request.user.email
            )
        except NewsletterSubscription.DoesNotExist:
            pass

        return subscribed, email

    def get(self, request):
        subscribed, email = self._get_subscription_info(request.user)
        return render(
            request,
            "core/newsletter_subscription.html",
            context={
                "is_currently_subscribed": subscribed,
                "form": NewsletterSubscriptionForm(initial={"email": email}),
            },
        )

    def post(self, request):
        form = NewsletterSubscriptionForm(data=request.POST)

        if not form.is_valid():
            subscribed, _ = self._get_subscription_info(self.request.user)
            messages.error(request, "Form not valid")
            return render(
                request,
                "core/newsletter_subscription.html",
                context={
                    "is_currently_subscribed": subscribed,
                    "form": form,
                },
            )

        subscription, _ = NewsletterSubscription.objects.get_or_create(user=request.user)

        should_subscribe = form.cleaned_data.get("submit_action") == "subscribe"
        subscription.is_active = should_subscribe

        if should_subscribe:
            subscription.email_address = form.cleaned_data.get("email")

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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["trying_to_do_initial"] = self.request.GET.getlist("survey_source")
        return kwargs

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
            trying_to_do_other_message=cleaned["trying_to_do_other_message"],
            survey_source=cleaned["survey_source"],
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
    elif not (view_exists(database, schema, table) or table_exists(database, schema, table)):
        return HttpResponseNotFound()
    else:
        return table_data(request.user.email, database, schema, table)


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
                return HttpResponse(status=ex.response["ResponseMetadata"]["HTTPStatusCode"])
            except KeyError:
                return HttpResponseServerError()

        response = StreamingHttpResponseWithoutDjangoDbConnection(
            file_object["Body"].iter_chunks(chunk_size=65536),
            content_type=file_object["ContentType"],
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.split(path)[-1].rpartition("!")[0]}"'
        )
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
        try:
            return JsonResponse(
                get_dataflow_dag_status(get_data_flow_import_pipeline_name(), execution_date)
            )
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)


class CreateTableDAGTaskStatusView(View):
    def get(self, request, execution_date, task_id):
        try:
            return JsonResponse(
                {
                    "state": get_dataflow_task_status(
                        get_data_flow_import_pipeline_name(), execution_date, task_id
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


class ContactUsView(FormView):
    form_class = ContactUsForm
    template_name = "core/contact-us.html"

    def form_valid(self, form):
        cleaned = form.cleaned_data
        if cleaned["contact_type"] == form.ContactTypes.GET_HELP:
            return HttpResponseRedirect(reverse("support"))
        return HttpResponseRedirect(reverse("feedback"))


class SetNotificationCookie(View):
    def post(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        banner = NotificationBanner.objects.filter(published=True).first()
        if banner is None:
            return JsonResponse(
                {"message": "No published notification banners available."}, status=404
            )
        body = json.loads(request.body.decode())
        action = body.get("action")
        notification_action_values = ["accepted", "dismissed"]
        if action not in notification_action_values:
            return JsonResponse(
                {
                    "message": f"'action' parameter values must be one of: \
                    {', '.join(notification_action_values)}. Your arg: {action}."
                },
                status=400,
            )
        date_expiry = banner.end_date
        if datetime.now(timezone.utc).date() >= date_expiry:
            return JsonResponse(
                {"message": f"campaign {banner.campaign_name} expired"}, status=400
            )

        if is_last_days_remaining_notification_banner(banner) is True:
            # If doing any action (dismissing) during the last chance window the window
            # seeing the banner or your second time dismissing (first time as non last-chance,
            # second as last-chance). Therefore set as 'accepted' as 'dismissed' with the
            # last-chance logic means it would keep on showing.
            action = "accepted"
        response = JsonResponse({"message": f"banner {banner.campaign_name} {action}"}, status=200)
        response.set_cookie(
            banner.campaign_name,
            action,
            expires=date_expiry.strftime("%a, %d-%b-%Y %H:%M:%S GMT"),
            httponly=True,
            samesite="Lax",
            secure=True,
        )
        return response
