import logging
import os
import uuid
from datetime import datetime
from urllib.parse import urlencode
from django.db.models import Q


from aiohttp import ClientError
from django.conf import settings
from django.contrib.auth import get_user_model

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
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import DataSet, DataSetUserPermission, RequestingDataset, SourceTable, VisualisationUserPermission
from dataworkspace.apps.datasets.requesting_data.forms import DataSetOwnersForm, DatasetNameForm, DatasetDescriptionsForm, DatasetDataOriginForm
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.views import UserSearchFormView
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.your_files.utils import get_s3_csv_file_info
from dataworkspace.apps.your_files.views import RequiredParameterGetRequestMixin
from dataworkspace.forms import GOVUKDesignSystemRadioField, GOVUKDesignSystemRadiosWidget, GOVUKDesignSystemTextareaField, GOVUKDesignSystemTextareaWidget

logger = logging.getLogger(__name__)


class DatasetNameView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DatasetNameForm

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.create(
            name=form.cleaned_data.get("name"), type=DataSetType.MASTER)

        return HttpResponseRedirect(
            reverse(
                "datasets:requesting_data:dataset-descriptions",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatasetDescriptionsView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DatasetDescriptionsForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["title"] = "Summary information"
        context["link"] = "www.google.com"
        context["link_text"] = "Find out the best practice for writing descriptions."
        return context

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))
        requesting_dataset.short_description = form.cleaned_data.get("short_description")
        requesting_dataset.description = form.cleaned_data.get("description")

        return HttpResponseRedirect(
            reverse(
                "datasets:requesting_data:dataset-data-origin",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatasetDataOriginView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DatasetDataOriginForm

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))
        requesting_dataset.data_origin = form.cleaned_data.get("data_origin")

        return HttpResponseRedirect(
            reverse(
                "datasets:requesting_data:dataset-owners",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatasetOwnersView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DataSetOwnersForm

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))
        User = get_user_model()
        print('HELLOOOOOOOO')
        for user in User.objects.all():
            print(user.__dict__)
        # requesting_dataset.information_asset_owner = form.cleaned_data.get("information_asset_owner")





class BaseAddTableTemplateView(RequiredParameterGetRequestMixin, TemplateView):

    section_title = str
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
