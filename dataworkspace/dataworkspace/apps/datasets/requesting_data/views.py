import re
from django.forms import model_to_dict
from dataworkspace.tests.conftest import user
from formtools.preview import FormPreview
from formtools.wizard.views import NamedUrlSessionWizardView
from django.contrib.auth import get_user_model

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.datasets.models import DataSet, RequestingDataset

from django.db.models import Q

from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetOwnersForm,
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
    DatasetExistingSystemForm,
    DatasetLicenceForm,
    DatasetRestrictionsForm,
    DatasetUsageForm,
    DatasetLocationRestrictionsForm,
    DatasetNetworkRestrictionsForm,
    DatasetUserRestrictionsForm,
    DatasetIntendedAccessForm,
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetPersonalDataForm,
    DatasetCommercialSensitiveForm,
    DatasetRetentionPeriodForm,
    DatasetUpdateFrequencyForm,
    DatasetIAOForm,
    SummaryPageForm,
    TrackerPageForm
)


class RequestingDataWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("origin", DatasetDataOriginForm),
        ("iao", DatasetIAOForm),
        # ("owners", DatasetOwnersForm),
        # ("existing-system", DatasetExistingSystemForm),
        # ("licence", DatasetLicenceForm),
        # ("restrictions", DatasetRestrictionsForm),
        # ("usage", DatasetUsageForm),
        # ("security-classification", DatasetSecurityClassificationForm),
        # ("personal-data", DatasetPersonalDataForm),
        # ("special-personal-data", DatasetSpecialPersonalDataForm),
        # ("commercial-sensitive", DatasetCommercialSensitiveForm),
        # ("retention-period", DatasetRetentionPeriodForm),
        # ("update-frequency", DatasetUpdateFrequencyForm),
        # ("intended-access", DatasetIntendedAccessForm),
        # ("location-restrictions", DatasetLocationRestrictionsForm),
        # ("network-restrictions", DatasetNetworkRestrictionsForm),
        # ("user-restrictions", DatasetUserRestrictionsForm),
    ]

    def get_template_names(self):
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        if self.steps.current == "update-frequency":
            return "datasets/requesting_data/update_frequency_options.html"
        if self.steps.current == "iao":
            return "datasets/requesting_data/user_search.html"
        else:
            return "datasets/requesting_data/summary_information.html"
        
    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "iao":
            try: 
                search_query = self.request.GET.dict()["search"]
                context["search_query"] = search_query
                if search_query:
                        User = get_user_model()
                        search_query = search_query.strip()
                        email_filter = Q(email__icontains=search_query)
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

                        context["search_results"] = search_results
            except:
                return context
        return context

    notes_fields = [
            "origin",
            "existing_system",
            "special_personal_data",
            "commercial_sensitive",
            "update_frequency",
            "user_restrictions",
            "operational_impact",
            "location_restrictions",
            "network_restrictions",
            "user_restrictions",
        ]

    def get_template_names(self):
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        if self.steps.current == "update-frequency":
            return "datasets/requesting_data/update_frequency_options.html"
        if self.steps.current == "summary":
            return "datasets/requesting_data/summary.html"
        if self.steps.current == "iao":
            return "datasets/requesting_data/user_search.html"
        else:
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
            "operational_impact" "location_restrictions",
            "network_restrictions",
            "security_clearance",
            "user_restrictions",
        ]
        # these fields need to added to notes as they no do have fields themselves but are useful to analysts.
        User = get_user_model()

        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.save()

        # DatasetUsageForm to be sent to restrictions on usage.

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

        data_dict = model_to_dict(
            requesting_dataset,
            exclude=["id", "tags", "user", "sensitivity", "data_catalogue_editors", "stage_one_complete", "stage_two_complete"],
        )
        data_dict["enquiries_contact"] = requesting_dataset.enquiries_contact
        data_dict["information_asset_manager"] = requesting_dataset.information_asset_manager
        data_dict["information_asset_owner"] = requesting_dataset.information_asset_owner
        data_dict["slug"] = requesting_dataset.name.lower().replace(" ", "-")

        dataset = DataSet.objects.create(**data_dict)
        dataset.data_catalogue_editors.set(requesting_dataset.data_catalogue_editors.all())
        dataset.sensitivity.set(requesting_dataset.sensitivity.all())

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )





