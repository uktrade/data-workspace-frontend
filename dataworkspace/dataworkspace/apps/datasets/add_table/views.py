from datetime import datetime
import os
from urllib.parse import urlencode
import uuid
from venv import logger
from aiohttp import ClientError
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.core.exceptions import BadRequest
from django.views.generic import DetailView, FormView, TemplateView
from django.http import HttpResponseRedirect, HttpResponseServerError
from requests import HTTPError

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.add_table.forms import (
    TableNameForm,
    TableSchemaForm,
    DescriptiveNameForm,
    UploadCSVForm,
    AddTableDataTypesForm,
)
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.utils import copy_file_to_uploads_bucket, get_data_flow_import_pipeline_name, get_s3_prefix, trigger_dataflow_dag
from dataworkspace.apps.core.constants import SCHEMA_POSTGRES_DATA_TYPE_MAP, PostgresDataTypes
from dataworkspace.apps.your_files.utils import get_s3_csv_file_info
from dataworkspace.apps.your_files.views import ValidateSchemaMixin


class AddTableView(DetailView):
    template_name = "datasets/add_table/about_this_service.html"

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

    def _get_file_upload_key(self, file_name, pk):
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

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        client = get_s3_client()
        file_name = f"{csv_file.name}!{uuid.uuid4()}"
        key = self._get_file_upload_key(file_name, self.kwargs["pk"])
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

class AddTableDataTypesView(FormView):
    template_name = "datasets/add_table/data_types.html"
    form_class = AddTableDataTypesForm
    
    def _get_file_upload_key(self, file_name, pk):
        return os.path.join(
            get_s3_prefix(str(self.request.user.profile.sso_id)),
            "_add_table_uploads",
            str(pk),
            file_name,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "user": self.request.user,
                "column_definitions": get_s3_csv_file_info(self._get_file_upload_key(
                 self.kwargs["file_name"], self.kwargs["pk"]
            ))[
                    "column_definitions"
                ],
            }
        )
        return kwargs
    
    def form_invalid(self, form):
        print('FORM INVALID')
        print('form', form)

    def form_valid(self, form):
        source = self._get_source()
        print('blah_form_valid')
        cleaned = form.cleaned_data
        include_column_id = False

        file_info = get_s3_csv_file_info(cleaned["initial"]["path"])

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
            "descriptive_name": cleaned["descriptive_name"],
            "column_definitions": file_info["column_definitions"],
            "encoding": file_info["encoding"],
            "auto_generate_id_column": include_column_id,
        }

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

        return HttpResponseRedirect(
            reverse(
                "datasets:add_table")
            # f'{reverse("data")}?{urlencode(params)}'
        )


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        print('cxt:', ctx['view'].__dict__)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["source"] = dataset.sourcetable_set.all()
        ctx["model"] = dataset
        ctx["table_name"] = self.kwargs["table_name"]        
        ctx["backlink"] = reverse(
            "datasets:add_table:upload-csv",
            args=(self.kwargs["pk"], self.kwargs["schema"], self.kwargs["descriptive_name"], self.kwargs["table_name"]),
        )
        ctx["table_columns"] = []
        for x in ctx["model"].get_column_config():
            ctx["table_columns"].append(
                {
                    "field": x["field"],
                    "data_type": x["dataType"],
                }
            )
        ctx["file_columns"] = []
        for x in ctx["form"].column_definitions:
            ctx["file_columns"].append(
                {
                    "field": x["header_name"],
                    "data_type": x["data_type"],
                }
            )
        return ctx