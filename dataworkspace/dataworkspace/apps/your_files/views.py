from datetime import datetime, timedelta
from urllib.parse import urlencode

from csp.decorators import csp_update
from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView
from requests import HTTPError

from dataworkspace.apps.core.utils import (
    db_role_schema_suffix_for_user,
    get_s3_prefix,
    get_team_schemas_for_user,
    is_user_in_teams,
    new_private_database_credentials,
    postgres_user,
    source_tables_for_user,
)
from dataworkspace.apps.your_files.constants import PostgresDataTypes
from dataworkspace.apps.your_files.forms import (
    CreateTableDataTypesForm,
    CreateTableForm,
    CreateTableSchemaForm,
)
from dataworkspace.apps.your_files.utils import (
    clean_db_identifier,
    copy_file_to_uploads_bucket,
    get_dataflow_dag_status,
    get_dataflow_task_status,
    get_s3_csv_column_types,
    get_schema_for_user,
    get_user_schema,
    trigger_dataflow_dag,
    SCHEMA_POSTGRES_DATA_TYPE_MAP,
)


def file_browser_html_view(request):
    return file_browser_html_GET(request) if request.method == "GET" else HttpResponse(status=405)


@csp_update(CONNECT_SRC=["https://s3.eu-west-2.amazonaws.com"])
def file_browser_html_GET(request):
    prefix = get_s3_prefix(str(request.user.profile.sso_id))

    return render(
        request,
        "your_files/files.html",
        {"prefix": prefix, "bucket": settings.NOTEBOOKS_BUCKET},
        status=200,
    )


class RequiredParameterGetRequestMixin:
    required_parameters = []

    def get(self, request, *args, **kwargs):
        for param in self.required_parameters:
            if param not in self.request.GET:
                return HttpResponseBadRequest(f"Expected a `{param}` parameter")
        return super().get(request, *args, **kwargs)


class CreateTableView(RequiredParameterGetRequestMixin, TemplateView):
    template_name = "your_files/create-table-confirm.html"
    required_parameters = ["path"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        path = self.request.GET["path"]
        context.update(
            {
                "path": path,
                "filename": path.split("/")[-1],
                "table_name": clean_db_identifier(path),
                "show_schema": is_user_in_teams(self.request.user),
            }
        )
        return context


class CreateTableConfirmSchemaView(RequiredParameterGetRequestMixin, FormView):
    template_name = "your_files/create-table-confirm-schema.html"
    form_class = CreateTableSchemaForm

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            initial.update(
                {
                    "path": self.request.GET["path"],
                    "schema": self.request.GET.get("schema"),
                    "table_name": self.request.GET.get("table_name"),
                },
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user_schema = get_schema_for_user(self.request.user)
        team_schemas = get_team_schemas_for_user(self.request.user)
        schemas = [{"name": "user", "schema_name": user_schema}] + team_schemas
        schema_name = [
            schema["schema_name"]
            for schema in schemas
            if schema["name"] == form.cleaned_data["schema"]
        ]
        params = {
            "path": self.request.GET["path"],
            "schema": schema_name[0],
            "team": form.cleaned_data["schema"],
            "table_name": self.request.GET.get("table_name"),
        }
        return HttpResponseRedirect(
            f'{reverse("your-files:create-table-confirm-name")}?{urlencode(params)}'
        )


class CreateTableConfirmNameView(RequiredParameterGetRequestMixin, FormView):
    template_name = "your_files/create-table-confirm-name.html"
    form_class = CreateTableForm
    required_parameters = ["path"]

    def get_initial(self):
        schema = self.request.GET.get("schema", get_user_schema(self.request))
        initial = super().get_initial()
        if self.request.method == "GET":
            initial.update(
                {
                    "path": self.request.GET["path"],
                    "schema": schema,
                    "team": self.request.GET.get("team"),
                    "table_name": self.request.GET.get("table_name"),
                    "force_overwrite": "overwrite" in self.request.GET,
                }
            )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"show_schema": is_user_in_teams(self.request.user)})
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        params = {
            "path": form.cleaned_data["path"],
            "schema": form.cleaned_data["schema"],
            "table_name": form.cleaned_data["table_name"],
            "overwrite": form.cleaned_data["force_overwrite"],
        }
        return HttpResponseRedirect(
            f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}'
        )

    def form_invalid(self, form):
        errors = form.errors.as_data()

        # If path validation failed for any reason redirect to the generic failed page
        if errors.get("path"):
            return HttpResponseRedirect(
                f'{reverse("your-files:create-table-failed")}?'
                f'filename={form.data["path"].split("/")[-1]}'
            )

        # If table name validation failed due to a duplicate table in the db confirm overwrite
        if errors.get("table_name") and errors["table_name"][0].code == "duplicate-table":
            params = {
                "path": form.cleaned_data["path"],
                "table_name": form.data["table_name"],
                "overwrite": True,
            }
            return HttpResponseRedirect(
                f'{reverse("your-files:create-table-table-exists")}?{urlencode(params)}'
            )

        # Otherwise just redisplay the form (likely an invalid table name)
        return super().form_invalid(form)


class CreateTableConfirmDataTypesView(FormView):
    template_name = "your_files/create-table-confirm-data-types.html"
    form_class = CreateTableDataTypesForm
    required_parameters = [
        "filename",
        "schema",
        "table_name",
    ]

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            initial.update(
                {
                    "path": self.request.GET["path"],
                    "schema": self.request.GET["schema"],
                    "table_name": self.request.GET["table_name"],
                    "force_overwrite": "overwrite" in self.request.GET,
                }
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "user": self.request.user,
                "column_definitions": get_s3_csv_column_types(self.request.GET["path"]),
            }
        )
        return kwargs

    def form_valid(self, form):
        # call new_private_database_credentials to make sure everything is set
        user = self.request.user
        source_tables = source_tables_for_user(user)
        db_role_schema_suffix = db_role_schema_suffix_for_user(user)
        db_user = postgres_user(user.email)
        duration = timedelta(hours=24)

        new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            db_user,
            user,
            duration,
        )

        cleaned = form.cleaned_data
        column_definitions = get_s3_csv_column_types(cleaned["path"])
        for field in column_definitions:
            field["data_type"] = SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                cleaned[field["column_name"]], PostgresDataTypes.TEXT
            )

        import_path = settings.DATAFLOW_IMPORTS_BUCKET_ROOT + "/" + cleaned["path"]
        copy_file_to_uploads_bucket(cleaned["path"], import_path)
        filename = cleaned["path"].split("/")[-1]
        try:
            response = trigger_dataflow_dag(
                import_path,
                cleaned["schema"],
                cleaned["table_name"],
                column_definitions,
                f'{cleaned["schema"]}-{cleaned["table_name"]}-{datetime.now().isoformat()}',
            )
        except HTTPError:
            return HttpResponseRedirect(
                f'{reverse("your-files:create-table-failed")}?' f"filename={filename}"
            )

        params = {
            "filename": filename,
            "schema": cleaned["schema"],
            "table_name": cleaned["table_name"],
            "execution_date": response["execution_date"],
        }
        return HttpResponseRedirect(
            f'{reverse("your-files:create-table-validating")}?{urlencode(params)}'
        )


class BaseCreateTableTemplateView(RequiredParameterGetRequestMixin, TemplateView):
    required_parameters = [
        "filename",
        "schema",
        "table_name",
        "execution_date",
    ]
    steps = 5
    step: int

    def _get_query_parameters(self):
        return {param: self.request.GET.get(param) for param in self.required_parameters}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(**{"steps": self.steps, "step": self.step}, **self._get_query_parameters())
        return context


class BaseCreateTableStepView(BaseCreateTableTemplateView):
    template_name = "your_files/create-table-processing.html"
    task_name: str
    next_step_url_name: str

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "task_name": self.task_name,
                "next_step": f"{reverse(self.next_step_url_name)}?{urlencode(self._get_query_parameters())}",
            }
        )
        return context


class CreateTableValidatingView(BaseCreateTableStepView):
    task_name = "get-table-config"
    next_step_url_name = "your-files:create-table-creating-table"
    step = 1

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "title": "Validating",
                "info_text": (
                    "Your CSV file is being validated against your chosen columns and data types."
                ),
            }
        )
        return context


class CreateTableCreatingTableView(BaseCreateTableStepView):
    task_name = "create-temp-tables"
    next_step_url_name = "your-files:create-table-ingesting"
    step = 2

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "title": "Creating temporary table",
                "info_text": (
                    "Data will be inserted into a temporary table and validated before "
                    "it is made available."
                ),
            }
        )
        return context


class CreateTableIngestingView(BaseCreateTableStepView):
    task_name = "insert-into-temp-table"
    next_step_url_name = "your-files:create-table-renaming-table"
    step = 3

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "title": "Inserting data",
                "info_text": "Once complete, your data will be validated and your table will be "
                "made available.",
            }
        )
        return context


class CreateTableRenamingTableView(BaseCreateTableStepView):
    task_name = "swap-dataset-table-datasets_db"
    next_step_url_name = "your-files:create-table-success"
    step = 4

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "title": "Renaming temporary table",
                "info_text": "This is the last step, your table is almost ready.",
            }
        )
        return context


class CreateTableSuccessView(BaseCreateTableTemplateView):
    template_name = "your_files/create-table-success.html"
    step = 5


class CreateTableFailedView(RequiredParameterGetRequestMixin, TemplateView):
    template_name = "your_files/create-table-failed.html"
    required_parameters = ["filename"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filename"] = self.request.GET["filename"]
        return context


class CreateTableTableExists(RequiredParameterGetRequestMixin, TemplateView):
    template_name = "your_files/create-table-table-exists.html"
    required_parameters = ["path", "table_name"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = CreateTableForm(
            initial={
                "path": self.request.GET["path"],
                "schema": get_user_schema(self.request),
                "table_name": self.request.GET.get("table_name"),
                "force_overwrite": True,
            },
            user=self.request.user,
        )
        return context


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
            return JsonResponse(get_dataflow_dag_status(execution_date))
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)


class CreateTableDAGTaskStatusView(View):
    def get(self, request, execution_date, task_id):
        try:
            return JsonResponse({"state": get_dataflow_task_status(execution_date, task_id)})
        except HTTPError as e:
            return JsonResponse({}, status=e.response.status_code)
