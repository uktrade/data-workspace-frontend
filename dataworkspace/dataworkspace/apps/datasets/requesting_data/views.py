from django.forms import model_to_dict
from django.views.generic import FormView, TemplateView
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse

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
                "name": request.name,
                "created_date": request.created_date,
                "progress": progress,
                "uuid": request.id,
            }
        context["requests"] = requests
        return context


class AddNewDataset(TemplateView):
    template_name = "datasets/requesting_data/add_new_dataset.html"


class RequestingDatasetBaseWizardView(NamedUrlSessionWizardView, FormPreview):

    user_search_pages = [
        "information-asset-owner",
        "information-asset-manager",
        "enquiries-contact",
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
        if step == "summary":
            return "datasets/requesting_data/summary.html"
        if step in self.user_search_pages:
            return "datasets/requesting_data/user_search.html"
        if step == "security-classification":
            return "datasets/requesting_data/security.html"
        if step == "security-classification":
            return "datasets/requesting_data/security.html"
        else:
            return "datasets/requesting_data/form_template.html"
        
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
                summary_list.append(
                    {
                        step: {"question": questions[key], "answer": value},
                    },
                )
        # for field in fields:
        #     summary_list.append(
        #         {
        #             "TO DO": {
        #                 "question": questions[field],
        #                 "answer": self.get_all_cleaned_data()[field],
        #             },
        #         },
        #     )
        return summary_list


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
        context["stage"] = "Summary Information"
        step = self.steps.current
        if self.steps.current == "name":
            context["backlink"] = reverse("datasets:add_table:table-schema")
        else:
            context["backlink"] = reverse("requesting-data-summary-information-step", args={self.steps.prev})

        if step == "information-asset-owner":
            context["label"] = "Name of Information Asset Owner"
            context["help_text"] = (
                "IAO's are responsible for ensuring information assets are handled and managed appropriately"
            )
            self.get_user_search_context(context, step)
        elif step == "information-asset-manager":
            context["label"] = "Name of Information Asset Manager"
            context["help_text"] = (
                "IAM's have knowledge and duties associated with an asset, and so often support the IAO"
            )
            self.get_user_search_context(context, step)
        elif step == "enquiries-contact":
            context["label"] = "Contact person"
            context["help_text"] = "Description of contact person"
            self.get_user_search_context(context, step)
        elif step == "summary":
            context["summary"] = self.get_summary_context()

        return context

    def done(self, form_list, **kwargs):
        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.user = self.request.user.id
        requesting_dataset.stage_one_complete = True
        requesting_dataset = self.add_fields(form_list, requesting_dataset, self.notes_fields)
        requesting_dataset.save()

        self.request.session["requesting_dataset"] = requesting_dataset.id
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
        step = self.steps.current
        context["stage"] = "About This Data"
        if self.steps.current == "security-classification":
            context["backlink"] = reverse("datasets:add_table:table-schema")
        else:
            context["backlink"] = reverse("requesting-data-about-this-data-step", args={self.steps.prev})
        if step == "summary":
            context["summary"] = self.get_summary_context()
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
        step = self.steps.current
        context["stage"] = "Access Restriction"
        if self.steps.current == "intended-access":
            context["backlink"] = reverse("datasets:add_table:table-schema")
        else:
            context["backlink"] = reverse("requesting-data-access-restrictions-step", args={self.steps.prev})
        if step == "summary":
            context["summary"] = self.get_summary_context()
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


class RequestingDataTrackerView(FormView):
    form_class = TrackerPageForm
    template_name = "datasets/requesting_data/tracker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.kwargs.get("requesting_dataset_id")
        )
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
        
        return context

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


class RequestingDatasetSubmission(TemplateView):
    template_name = "datasets/requesting_data/submission.html"