from formtools.preview import FormPreview
from formtools.wizard.views import NamedUrlSessionWizardView

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.datasets.models import RequestingDataset
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetOwnersForm,
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
    DatasetExistingSystemForm,
    DatasetPreviouslyPublishedForm,
    DatasetLicenceForm,
    DatasetRestrictionsForm,
    DatasetPurposeForm,
    DatasetUsageForm,
    DatasetCurrentAccessForm,
    DatasetLocationRestrictionsForm,
    DatasetNetworkRestrictionsForm,
    DatasetUserRestrictionsForm,
    DatasetIntendedAccessForm,
    DatasetSecurityClearanceForm,
)
from dataworkspace.apps.datasets.requesting_data.forms import DatasetOwnersForm, DatasetNameForm, DatasetDescriptionsForm, DatasetDataOriginForm
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import get_task_error_message_template

from dataworkspace.apps.datasets.models import RequestingDataset, SourceTable
from dataworkspace.apps.datasets.requesting_data.forms import DaatasetSecurityClassificationForm, DatasetNameForm, DatasetDescriptionsForm, DatasetDataOriginForm
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.your_files.views import RequiredParameterGetRequestMixin


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
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("origin", DatasetDataOriginForm),
        ("owners", DatasetOwnersForm),
        ('existing-system', DatasetExistingSystemForm),
        ('previously-published', DatasetPreviouslyPublishedForm),
        ('licence', DatasetLicenceForm),
        ('restrictions', DatasetRestrictionsForm),
        ('purpose', DatasetPurposeForm),
        ('usage', DatasetUsageForm),
        # ('security-classification', DatasetSecurityClassificationForm),
        # ('personal-data', DatasetPersonalDataForm),
        # ('special-personal-data', DatasetSpecialPersonalDataForm),
        # ('commercial-sensitive', DatasetCommercialSensitiveForm),
        # ('retention-period', DatasetRetentionPeriodForm),
        # ('update-frequency', DatasetUpdateFrequencyForm),
        ('current-access', DatasetCurrentAccessForm),
        ('intended-access', DatasetIntendedAccessForm),
        ('location-restrictions', DatasetLocationRestrictionsForm),
        ('security-clearance', DatasetSecurityClearanceForm),
        ('network-restrictions', DatasetNetworkRestrictionsForm),
        ('user-restrictions', DatasetUserRestrictionsForm),
    ]

    def get_template_names(self):
        return "datasets/requesting_data/summary_information.html"

    def done(self, form_list, **kwargs):

        notes_fields = [
            "origin",
            "existing_system",
            "previously_published",
            "usage",
            "purpose",
            "special-personal-data",
            "commercial-sensitive",
            "update-frequency",
            "current_access",
            "intended_access",
            "operational_impact"
            "location_restrictions",
            "network_restrictions",
            "security_clearance",
            "user_restrictions",
        ]

        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.save()

        for form in form_list:
            print(form.cleaned_data)
            for field in form.cleaned_data:
                if field in notes_fields and form.cleaned_data.get(field):
                    if requesting_dataset.notes:
                        requesting_dataset.notes += (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                        requesting_dataset.save()
                    else:
                        requesting_dataset.notes = (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                        requesting_dataset.save()
                else:
                    setattr(requesting_dataset, field, form.cleaned_data.get(field))
                requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
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
                "datasets:requesting_data:dataset-security-classification",
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
                "datasets:requesting_data:dataset-security-classification",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatasetSecurityClassificationView(FormView):
    form_class = DaatasetSecurityClassificationForm
    model = RequestingDataset
    template_name = "datasets/requesting_data/security.html"

    def form_valid(self, form):
        print(">>>>>>", form.cleaned_data.get("sensitivity").values_list('id', flat=True))

        requesting_dataset = RequestingDataset.objects.get(id=self.kwargs.get("id"))
        requesting_dataset.government_security_classification = form.cleaned_data.get("government_security_classification")
        # if requesting_dataset.government_security_classification == 2:
        #     requesting_dataset.sensitivity = form.cleaned_data.get("sensitivity").values_list('id')

        return HttpResponseRedirect(
            reverse(
                "datasets:requesting_data:dataset-security-classification",
                kwargs={"id": requesting_dataset.id},
            )
        )


class DatsetPersonalDataView(FormView):
    form_class = SupportForm
    template_name = "core/support.html"


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
