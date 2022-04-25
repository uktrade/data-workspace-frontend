import os
import uuid
from datetime import datetime
from urllib.parse import urlencode

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import BadRequest
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from psycopg2 import sql
from requests import HTTPError
from waffle.mixins import WaffleFlagMixin

from dataworkspace import datasets_db
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.utils import get_random_data_sample, get_s3_prefix
from dataworkspace.apps.datasets.manager.forms import (
    SourceTableUploadColumnConfigForm,
    SourceTableUploadForm,
)
from dataworkspace.apps.datasets.views import DatasetEditBaseView
from dataworkspace.apps.your_files.constants import PostgresDataTypes
from dataworkspace.apps.your_files.models import UploadedTable
from dataworkspace.apps.your_files.utils import (
    SCHEMA_POSTGRES_DATA_TYPE_MAP,
    copy_file_to_uploads_bucket,
    get_s3_csv_column_types,
    trigger_dataflow_dag,
)


class DatasetManageSourceTableView(WaffleFlagMixin, DatasetEditBaseView, FormView):
    template_name = "datasets/uploader/manage_source_table.html"
    waffle_flag = settings.DATA_UPLOADER_UI_FLAG
    form_class = SourceTableUploadForm

    def _get_file_upload_key(self, file_name, source_uuid):
        return os.path.join(
            get_s3_prefix(str(self.request.user.profile.sso_id)),
            "_source_table_uploads",
            str(source_uuid),
            file_name,
        )

    def _get_source(self):
        return get_object_or_404(self.dataset.sourcetable_set.all(), pk=self.kwargs["source_uuid"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["source"] = self._get_source()
        return ctx

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        client = get_s3_client()
        file_name = f"{csv_file.name}!{uuid.uuid4()}"
        key = self._get_file_upload_key(file_name, self.kwargs["source_uuid"])
        csv_file.seek(0)
        try:
            client.put_object(
                Body=csv_file,
                Bucket=settings.NOTEBOOKS_BUCKET,
                Key=key,
            )
        except ClientError as ex:
            # pylint: disable=raise-missing-from
            return HttpResponseServerError(
                "Error saving file: {}".format(ex.response["Error"]["Message"])
            )

        source = self._get_source()
        return HttpResponseRedirect(
            reverse(
                "datasets:manager:manage_source_table_column_config",
                args=(source.dataset_id, source.id),
            )
            + f"?file={file_name}"
        )


class DatasetManageSourceTableColumnConfigView(DatasetManageSourceTableView):
    template_name = "datasets/uploader/manage_source_table_column_config.html"
    waffle_flag = settings.DATA_UPLOADER_UI_FLAG
    form_class = SourceTableUploadColumnConfigForm

    def dispatch(self, request, *args, **kwargs):
        if "file" not in self.request.GET:
            raise BadRequest("Expected a `file` parameter")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            initial["path"] = self._get_file_upload_key(
                self.request.GET["file"], self.kwargs["source_uuid"]
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["column_definitions"] = get_s3_csv_column_types(
            self._get_file_upload_key(self.request.GET["file"], self.kwargs["source_uuid"])
        )
        return kwargs

    def form_valid(self, form):
        source = self._get_source()
        cleaned = form.cleaned_data
        columns = get_s3_csv_column_types(cleaned["path"])
        for field in columns:
            field["data_type"] = SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                cleaned[field["column_name"]], PostgresDataTypes.TEXT
            )

        import_path = settings.DATAFLOW_IMPORTS_BUCKET_ROOT + "/" + cleaned["path"]
        copy_file_to_uploads_bucket(cleaned["path"], import_path)
        filename = cleaned["path"].split("/")[-1]
        conf = {
            "file_path": import_path,
            "schema_name": source.schema,
            "table_name": source.table,
            "column_definitions": columns,
        }
        try:
            response = trigger_dataflow_dag(
                conf,
                settings.DATAFLOW_API_CONFIG["DATAFLOW_S3_IMPORT_DAG"],
                f"{source.schema}-{source.table}-{datetime.now().isoformat()}",
            )
        except HTTPError:
            return HttpResponseRedirect(
                f'{reverse("your-files:create-table-failed")}?' f"filename={filename}"
            )

        params = {
            "filename": filename,
            "schema": source.schema,
            "table_name": source.table,
            "execution_date": response["execution_date"],
        }
        return HttpResponseRedirect(
            f'{reverse("datasets:manager:upload-validating", args=(source.dataset_id, source.id))}?{urlencode(params)}'
        )


class BaseUploadSourceProcessingView(DatasetEditBaseView, TemplateView):
    template_name = "datasets/uploader/uploading.html"
    required_parameters = [
        "filename",
        "schema",
        "table_name",
        "execution_date",
    ]
    steps = 5
    step: int
    next_step_url_name: str
    task_name: str = None
    page_title: str = None
    page_info_text: str = None

    def _get_source(self):
        return get_object_or_404(self.dataset.sourcetable_set.all(), pk=self.kwargs["source_uuid"])

    def dispatch(self, request, *args, **kwargs):
        for param in self.required_parameters:
            if param not in self.request.GET:
                raise BadRequest(f"Expected a `{param}` parameter")
        return super().dispatch(request, *args, **kwargs)

    def _get_query_parameters(self):
        return {param: self.request.GET.get(param) for param in self.required_parameters}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self._get_source()
        next_url = reverse(
            f"datasets:manager:{self.next_step_url_name}", args=(source.dataset_id, source.id)
        )
        query_params = {param: self.request.GET.get(param) for param in self.required_parameters}
        context.update(
            {
                "source": source,
                "task_name": self.task_name,
                "next_step": f"{next_url}?{urlencode(query_params)}",
                "title": self.page_title,
                "info_text": self.page_info_text,
                **{"steps": self.steps, "step": self.step},
                **query_params,
            }
        )
        return context


class SourceTableUploadValidatingView(BaseUploadSourceProcessingView):
    task_name = "get-table-config"
    next_step_url_name = "upload-creating-table"
    step = 1
    page_title = "Validating"
    page_info_text = "Your CSV file is being validated against your chosen columns and data types."


class SourceTableUploadCreatingTableView(BaseUploadSourceProcessingView):
    task_name = "create-temp-tables"
    next_step_url_name = "upload-ingesting"
    step = 2
    page_title = "Creating temporary table"
    page_info_text = (
        "Data will be inserted into a temporary table and validated before it is made available."
    )


class SourceTableUploadIngestingView(BaseUploadSourceProcessingView):
    task_name = "insert-into-temp-table"
    next_step_url_name = "upload-renaming-table"
    step = 3
    page_title = "Inserting data"
    page_info_text = (
        "Once complete, your data will be validated and your table will be made available."
    )


class SourceTableUploadRenamingTableView(BaseUploadSourceProcessingView):
    task_name = "swap-dataset-table-datasets_db"
    next_step_url_name = "upload-success"
    step = 4
    page_title = "Renaming temporary table"
    page_info_text = "This is the last step, your table is almost ready."


class SourceTableUploadSuccessView(BaseUploadSourceProcessingView, TemplateView):
    next_step_url_name = "manage_source_table"
    template_name = "datasets/uploader/upload_success.html"
    step = 5

    def get(self, request, *args, **kwargs):
        UploadedTable.objects.get_or_create(
            schema=request.GET.get("schema"),
            table_name=request.GET.get("table_name"),
            created_by=self.request.user,
            data_flow_execution_date=datetime.strptime(
                request.GET.get("execution_date").split(".")[0], "%Y-%m-%dT%H:%M:%S"
            ),
        )
        return super().get(request, *args, **kwargs)


class SourceTableUploadFailedView(BaseUploadSourceProcessingView, TemplateView):
    next_step_url_name = "manage_source_table"
    step = 5
    template_name = "datasets/uploader/upload_failed.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filename"] = ctx["filename"].split("!")[0]
        return ctx


class SourceTableRestoreView(DatasetManageSourceTableView, DetailView):
    model = UploadedTable
    template_name = "datasets/uploader/restore.html"
    pk_url_kwarg = "version_id"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        table = self.get_object()
        db_name = list(settings.DATABASES_DATA.items())[0][0]
        table_name = (
            f"{table.table_name}_{table.data_flow_execution_date.strftime('%Y%m%dt%H%M%S_swap')}"
        )
        ctx.update(
            {
                "fields": datasets_db.get_columns(db_name, schema=table.schema, table=table_name),
                "records": [],
            }
        )
        if ctx["fields"]:
            rows = get_random_data_sample(
                db_name,
                sql.SQL(f"select * from {table.schema}.{table_name}"),
                settings.DATASET_PREVIEW_NUM_OF_ROWS,
            )
            ctx["records"] = [
                {column: row[i] for i, column in enumerate(ctx["fields"])} for row in rows
            ]
        return ctx

    def post(self, request, *args, **kwargs):
        table = self.get_object()
        source = self._get_source()
        try:
            response = trigger_dataflow_dag(
                {
                    "ts_nodash": table.data_flow_execution_date.strftime("%Y%m%dt%H%M%S"),
                    "schema_name": table.schema,
                    "table_name": table.table_name,
                },
                settings.DATAFLOW_API_CONFIG["DATAFLOW_RESTORE_TABLE_DAG"],
                f"restore-{table.schema}-{table.table_name}-{datetime.now().isoformat()}",
            )
        except HTTPError:
            return HttpResponseRedirect(
                reverse(
                    "datasets:manager:restore-failed",
                    args=(source.dataset_id, source.id, table.id),
                )
            )

        params = {
            "execution_date": response["execution_date"],
            "task_name": "restore-swap-table-datasets_db",
        }
        return HttpResponseRedirect(
            reverse(
                "datasets:manager:restoring-table", args=(source.dataset_id, source.id, table.id)
            )
            + f"?{urlencode(params)}"
        )


class BaseRestoreVersionView(DatasetManageSourceTableView, TemplateView):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version"] = get_object_or_404(UploadedTable, pk=self.kwargs["version_id"])
        return ctx


class SourceTableRestoringView(BaseRestoreVersionView):
    template_name = "datasets/uploader/restoring.html"


class SourceTableRestoreFailedView(BaseRestoreVersionView):
    template_name = "datasets/uploader/restore_failed.html"


class SourceTableRestoreSuccessView(BaseRestoreVersionView):
    template_name = "datasets/uploader/restore_success.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version"] = get_object_or_404(UploadedTable, pk=self.kwargs["version_id"])
        return ctx
