from django.conf import settings
from django.forms import model_to_dict
from django.shortcuts import render
from django.views import View
from django.views.generic import FormView, TemplateView
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse

from csp.decorators import csp_update

from dataworkspace.apps.datasets.constants import SecurityClassificationAndHandlingInstructionType
from dataworkspace.apps.datasets.views import EditBaseView
from dataworkspace.zendesk import create_support_request
from formtools.preview import FormPreview  # pylint: disable=import-error
from formtools.wizard.views import NamedUrlSessionWizardView  # pylint: disable=import-error

from dataworkspace.apps.datasets.models import DataSet, RequestingDataset
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetCommercialSensitiveForm,
    DatasetEnquiriesContactForm,
    DatasetInformationAssetManagerForm,
    DatasetInformationAssetOwnerForm,
    DatasetIntendedAccessForm,
    DatasetLocationRestrictionsForm,
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
    DatasetExistingSystemForm,
    DatasetLicenceForm,
    DatasetNetworkRestrictionsForm,
    DatasetPersonalDataForm,
    DatasetRestrictionsForm,
    DatasetRetentionPeriodForm,
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetUpdateFrequencyForm,
    DatasetUsageForm,
    DatasetUserRestrictionsForm,
    SummaryPageForm,
    TrackerPageForm,
)


User = get_user_model()


class AddingData(TemplateView):
    template_name = "datasets/requesting_data/adding_data.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incomplete_requests = RequestingDataset.objects.filter(user=self.request.user.id)
        requests = {}
        for request in incomplete_requests:
            progress = 0
            if request.stage_one_complete:
                progress += 1
            if request.stage_two_complete:
                progress += 1
            if request.stage_three_complete:
                progress += 1
            requests[request.name] = {
                "id": request.id,
                "name": request.name,
                "created_date": request.created_date,
                "progress": progress,
                "uuid": request.id,
            }
        context["requests"] = requests
        return context


class AddNewDataset(TemplateView):
    template_name = "datasets/requesting_data/add_new_dataset.html"

    def get(self, request):
        previous_page = request.META["HTTP_REFERER"]
        if '/requesting-data/tracker/' in previous_page:
            RequestingDataset.objects.filter(id=self.request.session["requesting_dataset"]).delete()
        return render(request, "datasets/requesting_data/add_new_dataset.html")

    def post(self, request, *args, **kwargs):
        requesting_dataset = RequestingDataset.objects.create()
        self.kwargs["requesting_dataset_id"] = requesting_dataset.id
        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class DeleteRequestingDatasetJourney(View):
    def get(self, request, requesting_dataset_id):
        RequestingDataset.objects.filter(id=requesting_dataset_id).delete()
        return HttpResponseRedirect(
            reverse(
                "adding-data"
            ))


class RequestingDataTrackerView(FormView):
    form_class = TrackerPageForm
    template_name = "datasets/requesting_data/tracker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.kwargs["requesting_dataset_id"]
        )
        self.request.session["requesting_dataset"] = requesting_dataset.id
        context["requesting_dataset_id"] = requesting_dataset.id

        # TODO refactor
        stage_one_complete = requesting_dataset.stage_one_complete
        stage_two_complete = requesting_dataset.stage_two_complete
        stage_three_complete = requesting_dataset.stage_three_complete
        context["stage_one_complete"] = stage_one_complete
        context["stage_two_complete"] = stage_two_complete
        context["stage_three_complete"] = stage_three_complete
        if stage_one_complete and stage_two_complete and stage_three_complete:
            context["all_stages_complete"] = True
        if not stage_one_complete and not stage_two_complete and not stage_three_complete:
            context["backlink"] = reverse("add-new-dataset")
        if "/requesting-data/summary-information/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-data")
        if "/requesting-data/about-this-data/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-data")
        if "/requesting-data/access-restrictions/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-data")
        if "/requesting-data/adding-data" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-data")

        # if step before was the last step of the section:
        #     context["backlink"] = "last step of the section"
        return context

    # def get(self, request, requesting_dataset_id):
    #     previous_page = request.META["HTTP_REFERER"]
    #     print("previous_page::::", previous_page)
    #     return render(request, "datasets/requesting_data/tracker.html")

    def form_valid(self, form):
        requesting_dataset = RequestingDataset.objects.get(
            id=form.cleaned_data["requesting_dataset"]
        )
        data_dict = model_to_dict(
            requesting_dataset,
            exclude=[
                "id",
                "tags",
                "user",
                "sensitivity",
                "data_catalogue_editors",
                "stage_one_complete",
                "stage_two_complete",
                "stage_three_complete",
            ],
        )
        # TODO refactor
        data_dict["enquiries_contact"] = requesting_dataset.enquiries_contact
        data_dict["information_asset_manager"] = requesting_dataset.information_asset_manager
        data_dict["information_asset_owner"] = requesting_dataset.information_asset_owner
        data_dict["slug"] = requesting_dataset.name.lower().replace(" ", "-")

        dataset = DataSet.objects.create(**data_dict)
        dataset.data_catalogue_editors.set(requesting_dataset.data_catalogue_editors.all())
        dataset.sensitivity.set(requesting_dataset.sensitivity.all())
        dataset.save()

        RequestingDataset.objects.filter(id=requesting_dataset.id).delete()

        # zendesk_ticket_id = create_support_request(
        #     self.request.user,
        #     User.objects.get(id=requesting_dataset.user).email,
        #     ["A new dataset has been requested."],
        # )

        return HttpResponseRedirect(
            reverse(
                "requesting-data-submission",
                # kwargs={"zendesk_ticket_id": zendesk_ticket_id},
            )
        )


class RequestingDatasetBaseWizardView(NamedUrlSessionWizardView, FormPreview):

    user_search_pages = [
        "information-asset-owner",
        "information-asset-manager",
        "enquiries-contact",
    ]

    radio_input_pages = [
        "licence",
        "usage",
        "personal-data",
        "special-personal-data",
        "commercial-sensitive",
        "location-restrictions",
        "network-restrictions",
        "user-restrictions",
    ]

    def add_fields(self, form_list, requesting_dataset, notes_fields):
        for form in form_list:
            for field in form.cleaned_data:
                if field in notes_fields and form.cleaned_data.get(field):
                    if requesting_dataset.notes:
                        requesting_dataset.notes += (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                    else:
                        requesting_dataset.notes = (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                    if field == "enquiries_contact":
                        requesting_dataset.enquiries_contact = User.objects.get(
                            id=form.cleaned_data.get(field).id
                        )
                if field == "sensitivity":
                    requesting_dataset.sensitivity.set(form.cleaned_data.get("sensitivity"))
                else:
                    setattr(requesting_dataset, field, form.cleaned_data.get(field))
            requesting_dataset.save()
        return requesting_dataset

    def get_users(self, search_query):
        email_filter = Q(email__icontains=search_query)
        if len(search_query.split(" ")) > 1:
            name_filter = Q(first_name__icontains=search_query.split()[0]) | Q(
                last_name__icontains=search_query.split(" ")[1]
            )
        else:
            name_filter = Q(first_name__icontains=search_query) | Q(
                last_name__icontains=search_query
            )
        users = User.objects.filter(Q(email_filter | name_filter))

        search_results = []

        for user in users:
            search_results.append(
                {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                }
            )

        return search_results

    def get_template(self, step):
        if step in  self.radio_input_pages:
            return "datasets/requesting_data/form_types/radio_input.html"
        if step in self.user_search_pages:
            return "datasets/requesting_data/form_types/user_search.html"
        if step == "security-classification":
            return "datasets/requesting_data/form_types/security_classification.html"
        if step == "summary":
            return "datasets/requesting_data/form_types/summary.html"
        else:
            return "datasets/requesting_data/form_types/basic_form.html"

    def get_user_search_context(self, context, step):
        context["form_page"] = step
        context["field"] = step.replace("-", "_")
        try:
            search_query = self.request.GET.dict()["search"]
            context["search_query"] = search_query
            if search_query:
                context["search_results"] = self.get_users(search_query=search_query.strip())
        except Exception:  # pylint: disable=broad-except
            return context

    def get_summary_context(self):
        summary_list = []
        questions = {}
        for name, form_item in self.form_list.items():  # pylint: disable=no-member
            for name, field in form_item.base_fields.items():
                questions[name] = field.label
        for step in self.storage.data["step_data"]:
            for key, value in self.get_cleaned_data_for_step(step).items():
                if key == "sensitivity":
                    continue
                if key == "government_security_classification":
                    if value == 1:
                        value = "Offiical"
                    if value == 2:
                        value = "Offiical-Sensitive"
                summary_list.append(
                    {
                        step: {"question": questions[key], "answer": value},
                    },
                )
        return summary_list
    
    def get_base_context(self, context, requesting_dataset, stage, step):
        if step in ["name", "security-classification", "intended-access"]:
            context["backlink"] = reverse("requesting-data-tracker", args={requesting_dataset.id})
        else:
            context["backlink"] = reverse(f"requesting-data-{stage}-step", args={self.steps.prev})

        if step in self.radio_input_pages:
            context["step"] = step
            current_form = self.get_form(step=step)
            radio_field = list(current_form.fields.keys())[0]
            input_field = list(current_form.fields.keys())[1]
            context["radio_field"] = radio_field
            context["radio_label"] = current_form.fields[radio_field].label
            context["input_field"] = input_field
            context["input_label"] = current_form.fields[input_field].label
        elif step == "summary":
            context["summary"] = self.get_summary_context()

        if step in self.user_search_pages:
            current_form = self.get_form(step=step)
            field = list(current_form.fields.keys())[0]
            context["label"] = current_form.fields[field].label
            context["help_text"] = current_form.fields[field].help_text
            self.get_user_search_context(context, step)

        return context


class RequestingDataSummaryInformationWizardView(RequestingDatasetBaseWizardView):
    form_list = [
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("origin", DatasetDataOriginForm),
        ("information-asset-owner", DatasetInformationAssetOwnerForm),
        ("information-asset-manager", DatasetInformationAssetManagerForm),
        ("enquiries-contact", DatasetEnquiriesContactForm),
        ("existing-system", DatasetExistingSystemForm),
        ("licence", DatasetLicenceForm),
        ("restrictions", DatasetRestrictionsForm),
        ("usage", DatasetUsageForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "name",
        "short_description",
        "description",
        "origin",
        "information_asset_owner",
        "information_asset_manager",
        "enquiries_contact",
        "existing_system",
        "licence",
        "restrictions",
        "usage",
    ]

    notes_fields = [
        "origin",
        "existing-system",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        context["stage"] = "Summary Information"
        step = self.steps.current
        self.get_base_context(context, requesting_dataset, "summary-information", step)

        if step == "descriptions":
            context["link_text"] = "Find out the best practice for writing descriptions."
            context["link"] = "https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/creating-and-updating-a-catalogue-pages/data-descriptions/"
        elif step in self.user_search_pages:
            context["link_text"] = "Find out more information about Security roles and responsibilities"
            context["link"] = "https://data-services-help.trade.gov.uk/data-workspace/how-to/data-owner-basics/managing-data-key-tasks-and-responsibilities/"

        return context

    def done(self, form_list, **kwargs):
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        requesting_dataset.user = self.request.user.id
        requesting_dataset.stage_one_complete = True
        requesting_dataset = self.add_fields(form_list, requesting_dataset, self.notes_fields)
        requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class RequestingDataAboutThisDataWizardView(RequestingDatasetBaseWizardView):

    form_list = [
        ("security-classification", DatasetSecurityClassificationForm),
        ("personal-data", DatasetPersonalDataForm),
        ("special-personal-data", DatasetSpecialPersonalDataForm),
        ("commercial-sensitive", DatasetCommercialSensitiveForm),
        ("retention-period", DatasetRetentionPeriodForm),
        ("update-frequency", DatasetUpdateFrequencyForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "government_security_classification",
        "personal_data",
        "special_personal_data",
        "commercial_sensitive",
        "retention_policy",
        "update_frequency",
    ]

    notes_fields = [
        "special-personal-data",
        "commercial-sensitive",
        "update-frequency",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        context["stage"] = "About This Data"
        step = self.steps.current
        self.get_base_context(context, requesting_dataset, "about-this-data", step)

        if step == "government_security_classification":
            context["link_text"] = "Find out more information about security classifications"
            context["link"] = "https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/creating-and-updating-a-catalogue-pages/set-the-security-classification-of-your-data/"
        elif step == "special_personal_data":
            context["link_text"] = "Find out more information about special category personal data"
            context["link"] = "NOT SURE !!!!"
    
        return context

    def done(self, form_list, **kwargs):
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        requesting_dataset = self.add_fields(form_list, requesting_dataset, self.notes_fields)
        requesting_dataset.stage_two_complete = True
        requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class RequestingDataAccessRestrictionsWizardView(RequestingDatasetBaseWizardView):

    form_list = [
        ("intended-access", DatasetIntendedAccessForm),
        ("location-restrictions", DatasetLocationRestrictionsForm),
        ("network-restrictions", DatasetNetworkRestrictionsForm),
        ("user-restrictions", DatasetUserRestrictionsForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "intended_access",
        "operational_impact",
        "location_restrictions",
        "network_restrictions",
        "user_restrictions",
    ]

    notes_fields = [
        "intended_access",
        "operational_impact",
        "location_restrictions",
        "network_restrictions",
        "user_restrictions",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        step = self.steps.current
        context["stage"] = "Access Restriction"
        self.get_base_context(context, requesting_dataset, "access-restrictions", step)

        if self.steps.current == "intended-access":
            context["backlink"] = reverse("requesting-data-tracker", args={requesting_dataset.id})
        else:
            context["backlink"] = reverse("requesting-data-access-restrictions-step", args={self.steps.prev})
        return context

    def done(self, form_list, **kwargs):
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        requesting_dataset = self.add_fields(form_list, requesting_dataset, self.notes_fields)
        requesting_dataset.stage_three_complete = True
        requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class RequestingDatasetSubmission(TemplateView):
    template_name = "datasets/requesting_data/submission.html"
