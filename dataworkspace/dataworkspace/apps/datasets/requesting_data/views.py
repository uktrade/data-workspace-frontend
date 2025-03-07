import logging
import os
import uuid
from datetime import datetime
from urllib.parse import urlencode
from django.db.models import Q
from formtools.preview import FormPreview
from formtools.wizard.views import SessionWizardView, NamedUrlWizardView, NamedUrlSessionWizardView


from aiohttp import ClientError
from django.conf import settings
from django.contrib.auth import get_user_model

from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from requests import HTTPError

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.constants import SCHEMA_POSTGRES_DATA_TYPE_MAP, PostgresDataTypes
from dataworkspace.apps.core.models import Database

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import DataSet, DataSetUserPermission, RequestingDataset, SourceTable, VisualisationUserPermission
from dataworkspace.apps.datasets.requesting_data.forms import DatasetOwnersForm, DatasetNameForm, DatasetDescriptionsForm, DatasetDataOriginForm, DatasetSystemForm
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.views import UserSearchFormView
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.your_files.utils import get_s3_csv_file_info
from dataworkspace.apps.your_files.views import RequiredParameterGetRequestMixin
from dataworkspace.forms import GOVUKDesignSystemRadioField, GOVUKDesignSystemRadiosWidget, GOVUKDesignSystemTextareaField, GOVUKDesignSystemTextareaWidget

logger = logging.getLogger(__name__)


class DatasetBaseView(FormView):
    def save_dataset(self, form, fields, page):
        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))
        for field in fields:
            setattr(requesting_dataset, field, form.cleaned_data.get(field))
            requesting_dataset.save()
        return HttpResponseRedirect(
            reverse(
                f"datasets:requesting_data:{page}",
            )
        )


class RequestingDataWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ('name', DatasetNameForm),
        ('descriptions', DatasetDescriptionsForm),
        ('origin', DatasetDataOriginForm),
        ('owners', DatasetOwnersForm),
#         # ('existing-system', DatasetExistingSystemForm),
#         # ('published', DatasetPublishedForm),
#         # ('licence', DatasetLicenceForm),
#         # ('restrictions', DatasetRestrictionsForm),
#         # ('purpose', DatasetPurposeForm),
#         # ('usage', DatasetUsageForm),
#         # ('security-classification', DatasetSecurityClassificationForm),
#         # ('personal-data', DatasetPersonalDataForm),
#         # ('special-personal-data', DatasetSpecialPersonalDataForm),
#         # ('commercial-sensitive', DatasetCommercialSensitiveForm),
#         # ('retention-period', DatasetRetentionPeriodForm),
#         # ('update-frequency', DatasetUpdateFrequencyForm),
#         # ('current-access', DatasetCurrentAccessForm),
#         # ('intended-access', DatasetIntendedAccessForm),
#         # ('location-restrictions', DatasetLocationRestrictionsForm),
#         # ('security-clearance', DatasetSecurityClearanceForm),
#         # ('network-restrictions', DatasetNetworkRestrictionsForm),
#         # ('user-restrictions', DatasetUserRestrictionsForm),
    ]

    def get_template_names(self):
        return "datasets/requesting_data/summary_information.html"
    
    # def process_step(self, form):
    #     """
    #     This method is used to postprocess the form data. By default, it
    #     returns the raw `form.data` dictionary.

    #     """

    #     print("HELLOOOO*************")
    #     print(form)
    #     print(form.prefix)
    #     print(form.cleaned_data)
    #     print(self.get_form_step_data(form))


    #     # During the process, get_cleaned_data_for_step will trigger an error
    #     # if some optional forms have been submitted, then later the user chooses a different path.
    #     # At the root of the branching paths, we need to remove step data if we jump to a different path
    #     # so we do not cause a keyerror when looping cleaned_data on the final barrier summary step.
    #     # if (
    #     #     form.prefix == "barrier-public-eligibility"
    #     #     and not form.cleaned_data["public_eligibility"]
    #     # ):
    #     #     for form_name in [
    #     #         "barrier-public-information-gate",
    #     #         "barrier-public-title",
    #     #         "barrier-public-summary",
    #     #     ]:
    #     #         if form_name in self.storage.data["step_data"]:
    #     #             self.storage.data["step_data"].pop(form_name)
    #     # if (
    #     #     form.prefix == "barrier-public-information-gate"
    #     #     and form.cleaned_data["public_information"] == "false"
    #     # ):
    #     #     for form_name in ["barrier-public-title", "barrier-public-summary"]:
    #     #         if form_name in self.storage.data["step_data"]:
    #     #             self.storage.data["step_data"].pop(form_name)

    #     return self.get_form_step_data(form)
    
    # def post(self, *args, **kwargs):
    #     print('HELLOOOOOOOOO')
    #     print(self)

    #     return HttpResponseRedirect(
    #         reverse(
    #             "datasets:requesting_data",
    #             kwargs={"step"="descriptions"},
    #         )
    #     )

#     # send a zendesk ticket and create object

    def done(self, form_list, **kwargs):

        for form in form_list:
            print(">>>>", form.prefix)
            print(">>>>", form.cleaned_data)

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )


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


class DatasetDescriptionsView(DatasetBaseView):
    form_class = DatasetDescriptionsForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["link"] = "www.google.com"
        context["link_text"] = "Find out the best practice for writing descriptions."
        return context

    def form_valid(self, form):
        fields = ["short_description", "description"]
        return self.save_dataset(form, fields, "dataset-data-origin")


class DatasetDataOriginView(DatasetBaseView):
    form_class = DatasetDataOriginForm

    def form_valid(self, form):
        fields = ["data_origin"]
        return self.save_dataset(form, fields, "dataset-owners")


class DatasetOwnersView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DatasetOwnersForm

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))

        requesting_dataset.information_asset_owner = form.cleaned_data["iao_user"]
        requesting_dataset.information_asset_manager = form.cleaned_data["iam_user"]
        requesting_dataset.enquiries_contact = form.cleaned_data["enquiries_contact_user"]

        return HttpResponseRedirect(
            reverse(
                "datasets:requesting_data:dataset-system",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatasetSystemView(FormView):
    template_name = "datasets/requesting_data/summary_information.html"
    form_class = DatasetSystemForm


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
    


class ReportBarrierWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ("name", DatasetNameForm),
        ("barrier-status", DatasetDescriptionsForm),
    ]

    # Use a condition dict to indicate pages that may not load depending on branching
    # paths through the form. Call the method outside the class which will return a bool
    # to decide if the page should be included in the form_list.

    def get_template_names(self):
        return "datasets/requesting_data/summary_information.html"
    
    def get(self, request, *args, **kwargs):
        """
        At this point we should check if the user is returning via a draft url and clear
        the current session via self.storage.reset(), get the draft barrier and
        convert the data into step data using self.storage.data to resume the drafting process.

        For legacy drafts we need to populate each step.
        This is cumbersome though and all the fields would need to be mapped to the right step.

        We save the whole storage object on 'save and exit' skip to done and check to see
        if it is the last step.
        If it is the last step then we save to barrier as normal if not we save
        the storage object and barrier status as draft.

        If it is the last step then we save to barrier as normal if not we save the storage object and barrier
        status as draft

        This renders the form or, if needed, does the http redirects.
        """

        step_url = kwargs.get("step", None)

        # Handle legacy React app calls
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return self.ajax(request, *args, **kwargs)

        # Is it resuming a draft barrier
        if draft_barrier_id := kwargs.get("draft_barrier_id", None):
            draft_barrier = self.client.reports.get(id=draft_barrier_id)
            session_data = draft_barrier.new_report_session_data.strip()
            self.storage.reset()
            self.storage.set_step_data("meta", {"barrier_id": str(draft_barrier_id)})

            if session_data == "":
                # TODO - we could try and map the legacy data here to the relevant steps
                # Step through the formlist and fields and map to value in legact draft
                # e.g setting barrier title on the first form
                self.storage.set_step_data(
                    "barrier-name", {"title": draft_barrier.title}
                )
                self.storage.current_step = self.steps.first

            return redirect(self.get_step_url(self.steps.current))

        elif step_url == "skip":
            # Save the previously entered data
            self.save_report_progress()

            # Clear the cache for new report
            self.storage.reset()

            return HttpResponseRedirect(reverse("barriers:dashboard"))

        elif step_url is None:
            if "reset" in self.request.GET:
                self.storage.reset()
                self.storage.current_step = self.steps.first
            if self.request.GET:
                query_string = "?%s" % self.request.GET.urlencode()
            else:
                query_string = ""
            return redirect(self.get_step_url(self.steps.current) + query_string)

        # Is the current step the "done" name/view?
        elif step_url == self.done_step_name:
            last_step = self.steps.last
            form = self.get_form(
                step=last_step,
                data=self.storage.get_step_data(last_step),
                files=self.storage.get_step_files(last_step),
            )
            return self.render_done(form, **kwargs)

        # Is the url step name not equal to the step in the storage?
        # if yes, change the step in the storage (if name exists)
        elif step_url == self.steps.current:
            # When passing into the step, we need to save our previously entered
            # data.
            self.save_report_progress()

            # URL step name and storage step name are equal, render!
            form = self.get_form(
                data=self.storage.current_step_data,
                files=self.storage.current_step_files,
            )
            return self.render(form, **kwargs)

        elif step_url in self.get_form_list():
            self.storage.current_step = step_url
            return self.render(
                self.get_form(
                    data=self.storage.current_step_data,
                    files=self.storage.current_step_files,
                ),
                **kwargs,
            )
        # Invalid step name, reset to first and redirect.
        else:
            self.storage.current_step = self.steps.first
            return redirect(self.get_step_url(self.steps.first))

    def save_report_progress(self):
        pass


    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        # Determine the step if not given
        if step is None:
            step = self.steps.current


        return form






