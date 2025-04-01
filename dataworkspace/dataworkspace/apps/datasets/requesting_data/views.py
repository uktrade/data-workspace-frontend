from django.forms import model_to_dict
from django.views.generic import FormView, TemplateView
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse

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


def add_fields(form_list, requesting_dataset, notes_fields):
    User = get_user_model()

    for form in form_list:
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


class AddingData(TemplateView):
    template_name = "datasets/requesting_data/adding_data.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incomplete_requests = RequestingDataset.objects.filter(user=self.request.user.id)
        print("incomplete_requests", incomplete_requests)
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


class RequestingDataSummaryInformationWizardView(NamedUrlSessionWizardView, FormPreview):
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

    user_search_pages = [
        "information-asset-owner",
        "information-asset-manager",
        "enquiries-contact",
    ]

    def get_users(self, search_query):
        User = get_user_model()
        search_query = search_query.strip()
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

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        step = self.steps.current

        if step == "information-asset-owner":
            context["label"] = "Name of Information Asset Owner"
            context["help_text"] = (
                "IAO's are responsible for ensuring information assets are handled and managed appropriately"
            )
        elif step == "information-asset-manager":
            context["label"] = "Name of Information Asset Manager"
            context["help_text"] = (
                "IAM's have knowledge and duties associated with an asset, and so often support the IAO"
            )
        elif step == "enquiries-contact":
            context["label"] = "Contact person"
            context["help_text"] = "Description of contact person"

        if step in self.user_search_pages:
            step = self.steps.current
            context["form_page"] = step
            context["field"] = step.replace("-", "_")
            try:
                search_query = self.request.GET.dict()["search"]
                context["search_query"] = search_query
                if search_query:
                    context["search_results"] = self.get_users(search_query=search_query)
            except Exception:  # pylint: disable=broad-except
                return context

        # could be abstracted
        if self.steps.current == "summary":

            # the field label in the forms
            section_one_fields = [
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

            section = []
            questions = {}
            for name, form_item in self.form_list.items():  # pylint: disable=no-member
                for name, field in form_item.base_fields.items():
                    question = field.label
                    questions[name] = question
            for field in section_one_fields:
                section.append(
                    {
                        "TO DO": {
                            "question": questions[field],
                            "answer": self.get_all_cleaned_data()[field],
                        },
                    },
                )
            context["summary"] = section
        context["stage"] = "Summary Information"

        return context

    notes_fields = [
        "origin",
        "existing_system",
        "special_personal_data",
    ]

    def get_template_names(self):
        user_search_pages = [
            "information-asset-owner",
            "information-asset-manager",
            "enquiries-contact",
        ]
        if self.steps.current == "summary":
            return "datasets/requesting_data/summary.html"
        if self.steps.current in user_search_pages:
            return "datasets/requesting_data/user_search.html"
        else:
            return "datasets/requesting_data/form_template.html"

    def done(self, form_list, **kwargs):
        user_id = self.request.user.id

        notes_fields = [
            "origin",
            "existing_system",
            "usage",
        ]

        # these fields need to added to notes as they no do have fields themselves but are useful to analysts.

        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.save()

        # DatasetUsageForm to be sent to restrictions on usage.
        requesting_dataset = add_fields(form_list, requesting_dataset, notes_fields)
        requesting_dataset.user = user_id
        requesting_dataset.stage_one_complete = True
        requesting_dataset.save()
        self.request.session["requesting_dataset"] = requesting_dataset.id
        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class RequestingDataAboutThisDataWizardView(NamedUrlSessionWizardView, FormPreview):
    def get_template_names(self):

        if self.steps.current == "summary":
            return "datasets/requesting_data/summary.html"
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        else:
            return "datasets/requesting_data/form_template.html"

    form_list = [
        ("security-classification", DatasetSecurityClassificationForm),
        ("personal-data", DatasetPersonalDataForm),
        ("special-personal-data", DatasetSpecialPersonalDataForm),
        ("commercial-sensitive", DatasetCommercialSensitiveForm),
        ("retention-period", DatasetRetentionPeriodForm),
        ("update-frequency", DatasetUpdateFrequencyForm),
        ("summary", SummaryPageForm),
    ]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "summary":
            # the field label in the forms
            section_two_fields = [
                "government_security_classification",
                "personal_data",
                "special_personal_data",
                "commercial_sensitive",
                "retention_policy",
                "update_frequency",
            ]

            section = []
            questions = {}

            for name, form_item in self.form_list.items():  # pylint: disable=no-member
                for name, field in form_item.base_fields.items():
                    question = field.label
                    questions[name] = question
            for field in section_two_fields:
                section.append(
                    {
                        "TO DO": {
                            "question": questions[field],
                            "answer": self.get_all_cleaned_data()[field],
                        },
                    },
                )

            context["summary"] = section
        context["stage"] = "About This Data"
        return context

    def done(self, form_list, **kwargs):
        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        requesting_dataset.save()

        notes_fields = [
            "purpose",
            "special-personal-data",
            "commercial-sensitive",
            "update-frequency",
        ]

        # DatasetUsageForm to be sent to restrictions on usage.

        requesting_dataset = add_fields(form_list, requesting_dataset, notes_fields)
        requesting_dataset.stage_two_complete = True
        requesting_dataset.save()
        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )


class RequestingDataAccessRestrictionsWizardView(NamedUrlSessionWizardView, FormPreview):

    def get_template_names(self):
        if self.steps.current == "summary":
            return "datasets/requesting_data/summary.html"
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        else:
            return "datasets/requesting_data/form_template.html"

    form_list = [
        ("intended-access", DatasetIntendedAccessForm),
        ("location-restrictions", DatasetLocationRestrictionsForm),
        ("network-restrictions", DatasetNetworkRestrictionsForm),
        ("user-restrictions", DatasetUserRestrictionsForm),
        ("summary", SummaryPageForm),
    ]

    def done(self, form_list, **kwargs):

        notes_fields = [
            "intended_access",
            "operational_impact",
            "location_restrictions",
            "network_restrictions",
            "security_clearance",
            "user_restrictions",
        ]

        requesting_dataset = RequestingDataset.objects.get(
            id=self.request.session["requesting_dataset"]
        )
        requesting_dataset.save()

        # DatasetUsageForm to be sent to restrictions on usage.

        requesting_dataset = add_fields(form_list, requesting_dataset, notes_fields)
        requesting_dataset.stage_three_complete = True
        requesting_dataset.save()
        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_dataset_id": requesting_dataset.id},
            )
        )

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "summary":
            # the feild label in the forms
            section_three_fields = [
                "intended_access",
                "operational_impact",
                "location_restrictions",
                "network_restrictions",
                "user_restrictions",
            ]

            section = []
            questions = {}

            for name, form_item in self.form_list.items():  # pylint: disable=no-member
                for name, field in form_item.base_fields.items():
                    question = field.label
                    questions[name] = question
            for field in section_three_fields:
                section.append(
                    {
                        "TO DO": {
                            "question": questions[field],
                            "answer": self.get_all_cleaned_data()[field],
                        },
                    },
                )

            context["summary"] = section
        context["stage"] = "Access Restriction"
        return context


class RequestingDataTrackerView(FormView):
    form_class = TrackerPageForm
    template_name = "datasets/requesting_data/tracker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requesting_dataset = RequestingDataset.objects.get(
            id=self.kwargs.get("requesting_dataset_id")
        )

        stage_one_complete = requesting_dataset.stage_one_complete
        stage_two_complete = requesting_dataset.stage_two_complete
        stage_three_complete = requesting_dataset.stage_three_complete
        context["stage_one_complete"] = stage_one_complete
        context["stage_two_complete"] = stage_two_complete
        context["stage_three_complete"] = stage_three_complete
        if stage_one_complete and stage_two_complete and stage_three_complete:
            context["all_stages_complete"] = True
        context["requesting_dataset_id"] = requesting_dataset.id
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
        data_dict["enquiries_contact"] = requesting_dataset.enquiries_contact
        data_dict["information_asset_manager"] = requesting_dataset.information_asset_manager
        data_dict["information_asset_owner"] = requesting_dataset.information_asset_owner
        data_dict["slug"] = requesting_dataset.name.lower().replace(" ", "-")

        dataset = DataSet.objects.create(**data_dict)
        dataset.data_catalogue_editors.set(requesting_dataset.data_catalogue_editors.all())
        dataset.sensitivity.set(requesting_dataset.sensitivity.all())

        RequestingDataset.objects.filter(id=requesting_dataset.id).delete()

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )
