import logging
from datetime import datetime
from urllib.parse import urlencode

import waffle
from csp.decorators import csp_update
from django.conf import settings
from django.db.utils import ProgrammingError
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import DetailView, FormView, ListView, TemplateView
from psycopg2 import sql
from requests import HTTPError

from dataworkspace import datasets_db
from dataworkspace.apps.core.constants import SCHEMA_POSTGRES_DATA_TYPE_MAP, PostgresDataTypes
from dataworkspace.apps.core.utils import (
    clean_db_identifier,
    copy_file_to_uploads_bucket,
    create_new_schema,
    get_all_schemas,
    get_data_flow_import_pipeline_name,
    get_random_data_sample,
    get_s3_prefix,
    get_task_error_message_template,
    get_team_prefixes,
    get_team_schemas_for_user,
    trigger_dataflow_dag,
)
from dataworkspace.apps.your_files.forms import (
    CreateSchemaForm,
    CreateTableDataTypesForm,
    CreateTableForm,
    CreateTableSchemaForm,
)
from dataworkspace.apps.your_files.models import UploadedTable
from dataworkspace.apps.your_files.utils import (
    get_s3_csv_file_info,
    get_schema_for_user,
    get_user_schema,
)

logger = logging.getLogger("app")


@csp_update(
    CONNECT_SRC=settings.YOUR_FILES_CONNECT_SRC,
    SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC,
)
def your_files_home(request, s3_path=None):
    home_prefix = get_s3_prefix(str(request.user.profile.sso_id))
    initial_prefix = home_prefix if s3_path in [None, "/"] else s3_path
    teams_folders_prefixes = get_team_prefixes(request.user)
    return render(
        request,
        "your_files/files-react.html",
        {
            "teams_folders_prefixes": teams_folders_prefixes,
            "home_prefix": home_prefix,
            "initial_prefix": initial_prefix,
            "bucket": settings.NOTEBOOKS_BUCKET,
            "aws_endpoint": settings.S3_LOCAL_ENDPOINT_URL,
        },
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
        if self.request.user.is_staff:
            all_schemas = get_all_schemas() + ["new"]
        else:
            all_schemas = []

        user_schema = get_schema_for_user(self.request.user)
        team_schemas = get_team_schemas_for_user(self.request.user)
        schemas = (
            [{"name": "user", "schema_name": user_schema}]
            + team_schemas
            + [{"name": schema, "schema_name": schema} for schema in all_schemas]
        )
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

        if params["schema"] == "new":
            del params["schema"]
            target = f'{reverse("your-files:create-schema")}?{urlencode(params)}'
        else:
            target = f'{reverse("your-files:create-table-confirm-name")}?{urlencode(params)}'
        if url_has_allowed_host_and_scheme(target, settings.ALLOWED_HOSTS) is True:
            return HttpResponseRedirect(target)
        else:
            return HttpResponseRedirect("/")


class CreateSchemaView(FormView):
    template_name = "your_files/create-schema.html"
    form_class = CreateSchemaForm

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_staff:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        params = {
            "path": self.request.GET["path"],
            "schema": form.cleaned_data["schema"],
            "team": form.cleaned_data["schema"],
            "table_name": self.request.GET.get("table_name"),
        }
        try:
            create_new_schema(form.cleaned_data["schema"])
        except ProgrammingError as e:
            form.add_error(error=str(e), field="schema")
            return super().form_invalid(form)
        target = f'{reverse("your-files:create-table-confirm-name")}?{urlencode(params)}'
        if url_has_allowed_host_and_scheme(target, settings.ALLOWED_HOSTS) is True:
            return HttpResponseRedirect(target)
        else:
            return HttpResponseRedirect("/")


class ValidateSchemaMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET":
            schema = self.request.GET.get("schema", get_user_schema(self.request))
        else:
            schema = self.request.POST.get("schema", get_user_schema(self.request))

        if self.request.user.is_staff:
            self.all_schemas = get_all_schemas()
        else:
            self.all_schemas = []

        user_schema = get_schema_for_user(self.request.user)
        team_schemas = get_team_schemas_for_user(self.request.user)
        schemas = (
            [{"name": "user", "schema_name": user_schema}]
            + team_schemas
            + [{"name": schema, "schema_name": schema} for schema in self.all_schemas]
        )

        if schema not in [s["schema_name"] for s in schemas]:
            raise Http404

        return super().dispatch(request, *args, **kwargs)


class CreateTableConfirmNameView(RequiredParameterGetRequestMixin, ValidateSchemaMixin, FormView):
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
        if (
            not form.cleaned_data["force_overwrite"]
            and errors.get("table_name")
            and errors["table_name"][0].code == "duplicate-table"
        ):
            params = {
                "path": form.cleaned_data["path"],
                "table_name": form.data["table_name"],
                "schema": form.cleaned_data["schema"],
                "overwrite": form.cleaned_data["force_overwrite"],
            }
            target = f'{reverse("your-files:create-table-table-exists")}?{urlencode(params)}'
            if url_has_allowed_host_and_scheme(target, settings.ALLOWED_HOSTS) is True:
                return HttpResponseRedirect(target)
            else:
                return HttpResponseRedirect("/")

        # Otherwise just redisplay the form (likely an invalid table name)
        return super().form_invalid(form)


class CreateTableConfirmDataTypesView(ValidateSchemaMixin, FormView):
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
                    "table_exists_action": self.request.GET.get("table_exists_action"),
                }
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "user": self.request.user,
                "column_definitions": get_s3_csv_file_info(self.request.GET["path"])[
                    "column_definitions"
                ],
            }
        )
        return kwargs

    def form_valid(self, form):
        cleaned = form.cleaned_data
        include_column_id = False

        file_info = get_s3_csv_file_info(cleaned["path"])

        logger.info(file_info)

        for field in file_info["column_definitions"]:
            field["data_type"] = SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                cleaned[field["column_name"]], PostgresDataTypes.TEXT
            )

        import_path = settings.DATAFLOW_IMPORTS_BUCKET_ROOT + "/" + cleaned["path"]
        logger.debug("import_path %s", import_path)

        copy_file_to_uploads_bucket(cleaned["path"], import_path)

        filename = cleaned["path"].split("/")[-1]
        logger.debug(filename)

        if "auto_generate_id_column" in cleaned and cleaned["auto_generate_id_column"] != "":
            include_column_id = cleaned["auto_generate_id_column"] == "True"

        conf = {
            "file_path": import_path,
            "schema_name": cleaned["schema"],
            "table_name": cleaned["table_name"],
            "column_definitions": file_info["column_definitions"],
            "encoding": file_info["encoding"],
            "auto_generate_id_column": include_column_id,
        }
        if waffle.switch_is_active(settings.INCREMENTAL_S3_IMPORT_PIPELINE_FLAG):
            conf["incremental"] = (
                not cleaned.get("force_overwrite", False)
                and cleaned.get("table_exists_action") == "append"
            )

        logger.debug("Triggering pipeline %s", get_data_flow_import_pipeline_name())
        logger.debug(conf)
        if cleaned["schema"] not in self.all_schemas:
            conf["db_role"] = cleaned["schema"]

        try:
            response = trigger_dataflow_dag(
                conf,
                get_data_flow_import_pipeline_name(),
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
        if waffle.switch_is_active(settings.INCREMENTAL_S3_IMPORT_PIPELINE_FLAG):
            return HttpResponseRedirect(
                f'{reverse("your-files:create-table-appending")}?{urlencode(params)}'
            )

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
        query_params = self._get_query_parameters()
        query_params["task_name"] = self.task_name
        context.update(
            {
                "task_name": self.task_name,
                "next_step": f"{reverse(self.next_step_url_name)}?{urlencode(query_params)}",
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


class CreateTableAppendingToTableView(BaseCreateTableStepView):
    task_name = "sync"
    next_step_url_name = "your-files:create-table-success"
    step = 4

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        if waffle.switch_is_active(settings.INCREMENTAL_S3_IMPORT_PIPELINE_FLAG):
            context.update(
                {
                    "title": "Appending to existing table",
                    "info_text": "This is the last step, your table is almost ready.",
                }
            )
        else:
            context.update(
                {
                    "title": "Creating and inserting into your table",
                    "info_text": "This is the last step, your table is almost ready.",
                }
            )
        return context


class CreateTableSuccessView(BaseCreateTableTemplateView):
    template_name = "your_files/create-table-success.html"
    step = 5

    def get(self, request, *args, **kwargs):
        if "execution_date" in request.GET:
            UploadedTable.objects.get_or_create(
                schema=request.GET.get("schema"),
                table_name=request.GET.get("table_name"),
                data_flow_execution_date=datetime.strptime(
                    request.GET.get("execution_date").split(".")[0], "%Y-%m-%dT%H:%M:%S"
                ),
                created_by=self.request.user,
            )
        return super().get(request, *args, **kwargs)


class CreateTableFailedView(RequiredParameterGetRequestMixin, TemplateView):
    template_name = "your_files/create-table-failed.html"
    required_parameters = ["filename"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filename"] = self.request.GET["filename"]
        if "execution_date" in self.request.GET and "task_name" in self.request.GET:
            context["error_message_template"] = get_task_error_message_template(
                self.request.GET["execution_date"], self.request.GET["task_name"]
            )
        return context


class CreateTableTableExists(RequiredParameterGetRequestMixin, ValidateSchemaMixin, FormView):
    template_name = "your_files/create-table-table-exists.html"
    required_parameters = ["path", "table_name"]
    form_class = CreateTableForm

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            initial.update(
                {
                    "path": self.request.GET["path"],
                    "schema": self.request.GET.get("schema"),
                    "table_name": self.request.GET.get("table_name"),
                    "force_overwrite": True,
                },
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        params = {
            "path": form.cleaned_data["path"],
            "schema": form.cleaned_data["schema"],
            "table_name": form.cleaned_data["table_name"],
            "table_exists_action": form.cleaned_data.get("table_exists_action"),
        }
        return HttpResponseRedirect(
            f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}'
        )


class ValidateUserIsStaffMixin:
    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_staff:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class UploadedTableListView(ValidateUserIsStaffMixin, ListView):
    model = UploadedTable
    template_name = "your_files/uploaded-table-list.html"
    ordering = ["schema", "table_name"]


class RestoreTableView(ValidateUserIsStaffMixin, DetailView):
    model = UploadedTable
    template_name = "your_files/restore-table.html"

    def get_context_data(self, **kwargs):
        table = self.get_object()
        db_name = list(settings.DATABASES_DATA.items())[0][0]
        table_name = (
            f"{table.table_name}_{table.data_flow_execution_date.strftime('%Y%m%dt%H%M%S_swap')}"
        )
        schema_name = table.schema
        columns = datasets_db.get_columns(db_name, schema=schema_name, table=table_name)
        query = f"""
            select * from "{schema_name}"."{table_name}"
        """
        records = []
        sample_size = settings.DATASET_PREVIEW_NUM_OF_ROWS
        if columns:
            rows = get_random_data_sample(
                db_name,
                sql.SQL(query),
                sample_size,
            )
            for row in rows:
                record_data = {}
                for i, column in enumerate(columns):
                    record_data[column] = row[i]
                records.append(record_data)

        ctx = super().get_context_data(**kwargs)
        ctx["fields"] = columns
        ctx["records"] = records
        ctx["preview_limit"] = sample_size
        ctx["record_count"] = len(records)
        ctx["fixed_table_height_limit"] = (10,)
        ctx["truncate_limit"] = 100
        return ctx

    def post(self, request, *args, **kwargs):
        table = self.get_object()
        config = settings.DATAFLOW_API_CONFIG
        try:
            response = trigger_dataflow_dag(
                {
                    "ts_nodash": table.data_flow_execution_date.strftime("%Y%m%dt%H%M%S"),
                    "schema_name": table.schema,
                    "table_name": table.table_name,
                },
                config["DATAFLOW_RESTORE_TABLE_DAG"],
                f"restore-{table.schema}-{table.table_name}-{datetime.now().isoformat()}",
            )
        except HTTPError:
            return HttpResponseRedirect(
                f'{reverse("your-files:restore-table-failed", kwargs={"pk": table.id})}'
            )

        params = {
            "execution_date": response["execution_date"],
            "task_name": "restore-swap-table-datasets_db",
        }
        return HttpResponseRedirect(
            f'{reverse("your-files:restore-table-in-progress", kwargs={"pk": table.id})}?{urlencode(params)}'
        )


class RestoreTableViewInProgress(ValidateUserIsStaffMixin, DetailView):
    model = UploadedTable
    template_name = "your_files/restore-table-in-progress.html"


class RestoreTableViewFailed(ValidateUserIsStaffMixin, DetailView):
    model = UploadedTable
    template_name = "your_files/restore-table-failed.html"


class RestoreTableViewSuccess(ValidateUserIsStaffMixin, DetailView):
    model = UploadedTable
    template_name = "your_files/restore-table-success.html"
