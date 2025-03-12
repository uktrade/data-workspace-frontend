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


class RequestingDataWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("origin", DatasetDataOriginForm),
        ("owners", DatasetOwnersForm),
        ('existing-system', DatasetExistingSystemForm),
        ('published', DatasetPreviouslyPublishedForm),
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
            "published",
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
