from django.forms import model_to_dict
from formtools.preview import FormPreview
from formtools.wizard.views import NamedUrlSessionWizardView
from django.contrib.auth import get_user_model

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.datasets.models import DataSet, RequestingDataset

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
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetPersonalDataForm,
    DatasetCommercialSensitiveForm,
    DatasetRetentionPeriodForm,
    DatasetUpdateFrequencyForm
)


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
        ("existing-system", DatasetExistingSystemForm),
        ("previously-published", DatasetPreviouslyPublishedForm),
        ("licence", DatasetLicenceForm),
        ("restrictions", DatasetRestrictionsForm),
        ("purpose", DatasetPurposeForm),
        ("usage", DatasetUsageForm),
        ("security-classification", DatasetSecurityClassificationForm),
        ("personal-data", DatasetPersonalDataForm),
        ("special-personal-data", DatasetSpecialPersonalDataForm),
        ("commercial-sensitive", DatasetCommercialSensitiveForm),
        ("retention-period", DatasetRetentionPeriodForm),
        ("update-frequency", DatasetUpdateFrequencyForm),
        ("current-access", DatasetCurrentAccessForm),
        ("intended-access", DatasetIntendedAccessForm),
        ("location-restrictions", DatasetLocationRestrictionsForm),
        ("security-clearance", DatasetSecurityClearanceForm),
        ("network-restrictions", DatasetNetworkRestrictionsForm),
        ("user-restrictions", DatasetUserRestrictionsForm),
    ]

    def get_template_names(self):
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        if self.steps.current == "update-frequency":
            return "datasets/requesting_data/update_frequency_options.html"
        else:
            return "datasets/requesting_data/summary_information.html"

    def done(self, form_list, **kwargs):

        notes_fields = [
            "origin",
            "existing_system",
            "previously_published",
            "usage",
            "purpose",
            "special_personal_data",
            "commercial_sensitive",
            "update_frequency",
            "current_access",
            "user_restrictions",
            "operational_impact",
            "location_restrictions",
            "network_restrictions",
            "security_clearance",
            "user_restrictions",
        ]
        User = get_user_model()

        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.save()

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
            exclude=["id", "tags", "user", "sensitivity", "data_catalogue_editors"],
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
