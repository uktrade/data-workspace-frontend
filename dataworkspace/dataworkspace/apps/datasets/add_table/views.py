import logging
import os
import uuid
from datetime import datetime
from urllib.parse import urlencode

from aiohttp import ClientError
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from requests import HTTPError

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.constants import SCHEMA_POSTGRES_DATA_TYPE_MAP, PostgresDataTypes
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    copy_file_to_uploads_bucket,
    get_data_flow_import_pipeline_name,
    get_s3_prefix,
    get_task_error_message_template,
    trigger_dataflow_dag,
)
from dataworkspace.apps.datasets.add_table.forms import (
    AddTableDataTypesForm,
    DescriptiveNameForm,
    TableNameForm,
    TableSchemaForm,
    UploadCSVForm,
)
from dataworkspace.apps.datasets.models import SourceTable
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.your_files.utils import get_s3_csv_file_info
from dataworkspace.apps.your_files.views import RequiredParameterGetRequestMixin

logger = logging.getLogger(__name__)


class AddTableView(DetailView):
    template_name = "datasets/add_table/about_this_service.html"

    def dispatch(self, request, *args, **kwargs):
        source = self.get_object()
        if not source.user_can_add_table(self.request.user):
            return redirect(reverse("datasets:dataset_detail", args={self.kwargs["pk"]}))
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["backlink"] = reverse("datasets:dataset_detail", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})

        return ctx


class TableSchemaView(FormView):
    template_name = "datasets/add_table/table_schema.html"
    form_class = TableSchemaForm

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = self.get_schemas(dataset)
        schema_choices = list(((x, x) for x in schemas))
        initial.update(
            {
                "schema_choices": schema_choices,
            }
        )
        return initial

    def get_schemas(self, dataset):
        schemas = []
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            schemas.append(table.schema)

        return list(set(schemas))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = self.get_schemas(dataset)
        ctx["model_name"] = dataset.name
        ctx["model_id"] = self.kwargs["pk"]
        ctx["schema"] = schemas[0]
        ctx["is_multiple_schemas"] = len(schemas) > 1
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        return ctx

    def form_valid(self, form):
        clean_data = form.cleaned_data
        schema = clean_data["schema"]
        return HttpResponseRedirect(
            reverse("datasets:add_table:classification-check", args=(self.kwargs["pk"], schema))
        )


class ClassificationCheckView(TemplateView):
    template_name = "datasets/add_table/classification_check.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["model"] = dataset
        ctx["classification"] = (
            dataset.get_government_security_classification_display() or "Unclassified"
        ).title()
        ctx["backlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse(
            "datasets:add_table:descriptive-name", args=(self.kwargs["pk"], self.kwargs["schema"])
        )
        return ctx


class DescriptiveNameView(FormView):
    template_name = "datasets/add_table/descriptive_name.html"
    form_class = DescriptiveNameForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["model"] = dataset
        ctx["backlink"] = reverse(
            "datasets:add_table:classification-check",
            args=(self.kwargs["pk"], self.kwargs["schema"]),
        )
        return ctx

    def form_valid(self, form):
        descriptive_name = form.cleaned_data["descriptive_name"]
        return HttpResponseRedirect(
            reverse(
                "datasets:add_table:table-name",
                args=(self.kwargs["pk"], self.kwargs["schema"], descriptive_name),
            )
        )


class TableNameView(FormView):
    template_name = "datasets/add_table/table_name.html"
    form_class = TableNameForm

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        initial.update(
            {
                "schema": self.kwargs["schema"],
                "descriptive_name": self.kwargs["descriptive_name"],
                "table_names": self.get_all_table_names(),
            }
        )
        return initial

    def is_multiple_schemas(self, dataset):
        schemas = []
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            schemas.append(table.schema)

        return len(set(schemas)) > 1

    def get_all_table_names(self):
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        table_names = []
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            table_names.append(table.table)

        return table_names

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["is_multiple_schemas"] = self.is_multiple_schemas(dataset)
        ctx["model_name"] = dataset.name
        ctx["schema"] = self.kwargs["schema"]
        ctx["backlink"] = reverse(
            "datasets:add_table:descriptive-name",
            args=(self.kwargs["pk"], self.kwargs["schema"]),
        )
        return ctx

    def form_valid(self, form):
        table_name = form.cleaned_data["table_name"]
        return HttpResponseRedirect(
            reverse(
                "datasets:add_table:upload-csv",
                args=(
                    self.kwargs["pk"],
                    self.kwargs["schema"],
                    self.kwargs["descriptive_name"],
                    table_name,
                ),
            )
        )


class UploadCSVView(FormView):
    template_name = "datasets/add_table/upload_csv.html"
    form_class = UploadCSVForm

    def get_file_upload_key(self, file_name, pk):
        return os.path.join(
            get_s3_prefix(str(self.request.user.profile.sso_id)),
            "_add_table_uploads",
            str(pk),
            file_name,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["model"] = dataset
        ctx["backlink"] = reverse(
            "datasets:add_table:table-name",
            args=(self.kwargs["pk"], self.kwargs["schema"], self.kwargs["descriptive_name"]),
        )
        return ctx

    def form_invalid(self, form):
        return self.render_to_response({"timeout_error": True})

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        client = get_s3_client()
        file_name = f"{csv_file.name}!{uuid.uuid4()}"
        key = self.get_file_upload_key(file_name, self.kwargs["pk"])
        csv_file.seek(0)
        try:
            client.put_object(
                Body=csv_file,
                Bucket=settings.NOTEBOOKS_BUCKET,
                Key=key,
            )
        except ClientError as ex:
            # pylint: disable=raise-missing-from
            # pylint: disable=no-member
            return HttpResponseServerError(
                "Error saving file: {}".format(ex.response["Error"]["Message"])
            )

        return HttpResponseRedirect(
            reverse(
                "datasets:add_table:data-types",
                args=(
                    self.kwargs["pk"],
                    self.kwargs["schema"],
                    self.kwargs["descriptive_name"],
                    self.kwargs["table_name"],
                    file_name,
                ),
            )
        )


class AddTableDataTypesView(UploadCSVView):
    template_name = "datasets/add_table/data_types.html"
    form_class = AddTableDataTypesForm

    required_parameters = [
        "schema",
        "descriptive_name",
        "table_name",
        "file_name",
    ]

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            initial.update(
                {
                    "path": self.get_file_upload_key(self.kwargs["file_name"], self.kwargs["pk"]),
                    "schema": self.kwargs["schema"],
                    "descriptive_name": self.kwargs["descriptive_name"],
                    "table_name": self.kwargs["table_name"],
                    "file_name": self.kwargs["file_name"],
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
                "column_definitions": get_s3_csv_file_info(
                    self.get_file_upload_key(self.kwargs["file_name"], self.kwargs["pk"])
                )["column_definitions"],
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
            "schema_name": self.kwargs["schema"],
            "descriptive_name": self.kwargs["descriptive_name"],
            "table_name": self.kwargs["table_name"],
            "column_definitions": file_info["column_definitions"],
            "encoding": file_info["encoding"],
            "auto_generate_id_column": include_column_id,
        }

        logger.debug("Triggering pipeline %s", get_data_flow_import_pipeline_name())
        logger.debug(conf)

        try:
            response = trigger_dataflow_dag(
                conf,
                get_data_flow_import_pipeline_name(),
                f'{self.kwargs["schema"]}-{self.kwargs["table_name"]}-{datetime.now().isoformat()}',
            )
        except HTTPError:
            return HttpResponseRedirect(
                f'{reverse("datasets:add_table:create-table-failed")}?' f"filename={filename}"
            )

        params = {
            "descriptive_name": self.kwargs["descriptive_name"],
            "filename": self.kwargs["file_name"],
            "schema": self.kwargs["schema"],
            "table_name": self.kwargs["table_name"],
            "execution_date": response["execution_date"],
        }
        return HttpResponseRedirect(
            reverse("datasets:add_table:add-table-validating", args=(self.kwargs["pk"],))
            + "?"
            + urlencode(params)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["path"] = self.get_file_upload_key(self.kwargs["file_name"], self.kwargs["pk"])
        ctx["source"] = dataset.sourcetable_set.all()
        ctx["model"] = dataset
        ctx["table_name"] = self.kwargs["table_name"]
        ctx["backlink"] = reverse(
            "datasets:add_table:upload-csv",
            args=(
                self.kwargs["pk"],
                self.kwargs["schema"],
                self.kwargs["descriptive_name"],
                self.kwargs["table_name"],
            ),
        )

        return ctx


class BaseAddTableTemplateView(RequiredParameterGetRequestMixin, TemplateView):
    required_parameters = [
        "filename",
        "schema",
        "table_name",
        "execution_date",
        "descriptive_name",
    ]
    steps = 5
    step: int

    def _get_query_parameters(self):
        return {param: self.request.GET.get(param) for param in self.required_parameters}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(**{"steps": self.steps, "step": self.step}, **self._get_query_parameters())
        return context


class BaseAddTableStepView(BaseAddTableTemplateView):
    template_name = "datasets/add_table/create-table-processing.html"
    task_name: str
    next_step_url_name: str

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        query_params = self._get_query_parameters()
        query_params["task_name"] = self.task_name
        context.update(
            {
                "task_name": self.task_name,
                "next_step": f"{reverse(self.next_step_url_name, args=(self.kwargs['pk'],))}?{urlencode(query_params)}",
                "failure_url": f"{reverse('datasets:add_table:create-table-failed', args=(self.kwargs['pk'],))}?{urlencode(query_params)}",  # pylint: disable=line-too-long
            }
        )
        return context


class AddTableValidatingView(BaseAddTableStepView):
    task_name = "get-table-config"
    next_step_url_name = "datasets:add_table:add-table-creating-table"
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


class AddTableCreatingTableView(BaseAddTableStepView):
    task_name = "create-temp-tables"
    next_step_url_name = "datasets:add_table:add-table-ingesting"
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


class AddTableIngestingView(BaseAddTableStepView):
    task_name = "insert-into-temp-table"
    next_step_url_name = "datasets:add_table:add-table-renaming-table"
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


class AddTableRenamingTableView(BaseAddTableStepView):
    task_name = "swap-dataset-table-datasets_db"
    next_step_url_name = "datasets:add_table:add-table-success"
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


class AddTableAppendingToTableView(BaseAddTableStepView):
    task_name = "sync"
    next_step_url_name = "datasets:add_table:add-table-success"
    step = 4

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "title": "Creating and inserting into your table",
                "info_text": "This is the last step, your table is almost ready.",
            }
        )
        return context


class AddTableSuccessView(BaseAddTableTemplateView):

    template_name = "datasets/add_table/confirmation.html"
    step = 5
    default_download_limit = 5000

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        database = Database.objects.filter(memorable_name__contains="datasets").first()
        source_table, _ = SourceTable.objects.get_or_create(
            schema=self._get_query_parameters()["schema"],
            dataset=dataset,
            database=database,
            name=self._get_query_parameters()["descriptive_name"],
            table=self._get_query_parameters()["table_name"],
            data_grid_download_enabled=True,
            data_grid_download_limit=self.default_download_limit,
        )
        context["backlink"] = reverse("datasets:dataset_detail", args={self.kwargs["pk"]})
        context["edit_link"] = reverse("datasets:edit_dataset", args={self.kwargs["pk"]})
        context["model_name"] = source_table.name
        context["preview_link"] = reverse(
            "datasets:source_table_detail",
            kwargs={"dataset_uuid": self.kwargs["pk"], "object_id": source_table.id},
        )
        log_event(
            self.request.user,
            event_type=EventLog.TYPE_ADD_TABLE_TO_SOURCE_DATASET,
            related_object=dataset,
        )
        return context


class AddTableFailedView(BaseAddTableTemplateView):
    next_step_url_name = "manage-source-table"
    step = 5
    template_name = "datasets/add_table/upload_failed.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query_params = self._get_query_parameters()
        ctx["next_step"] = reverse(
            "datasets:add_table:upload-csv",
            args=(
                self.kwargs["pk"],
                query_params["schema"],
                query_params["descriptive_name"],
                query_params["table_name"],
            ),
        )
        if "execution_date" in self.request.GET and "task_name" in self.request.GET:
            ctx["error_message_template"] = get_task_error_message_template(
                self.request.GET["execution_date"], self.request.GET["task_name"]
            )
        return ctx
