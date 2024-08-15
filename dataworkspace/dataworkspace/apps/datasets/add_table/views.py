import os
import uuid
from aiohttp import ClientError
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from django.http import HttpResponseRedirect, HttpResponseServerError

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.add_table.forms import (
    TableNameForm,
    TableSchemaForm,
    DescriptiveNameForm,
    UploadCSVForm,
)
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.utils import get_s3_prefix


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
            table_names.append(table.name)

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
                args=(self.kwargs["pk"], self.kwargs["schema"], self.kwargs["descriptive_name"], table_name),
            )
        )

class UploadCSVView(FormView):
    template_name = "datasets/add_table/upload_csv.html"
    waffle_flag = settings.DATA_UPLOADER_UI_FLAG
    form_class = UploadCSVForm

    def _get_file_upload_key(self, file_name, source_uuid):
        return os.path.join(
            get_s3_prefix(str(self.request.user.profile.sso_id)),
            "_source_table_uploads", # will need to change 
            str(source_uuid),
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
        key = self._get_file_upload_key(file_name, self.kwargs["source_uuid"])
        csv_file.seek(0)
        try:
            client.put_object(
                Body=csv_file,
                Bucket=settings.NOTEBOOKS_BUCKET, # will need to change 
                Key=key,
            )
        except ClientError as ex:
            # pylint: disable=raise-missing-from
            return HttpResponseServerError(
                "Error saving file: {}".format(ex.response["Error"]["Message"])
            )

        return HttpResponseRedirect(
            reverse(
            "datasets:add_table:table-name",
            args=(self.kwargs["pk"], self.kwargs["schema"], self.kwargs["descriptive_name"], self.kwargs["table_name"]),
            )
            + f"?file={file_name}"
        )
    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse(
                "/",
            )
        )