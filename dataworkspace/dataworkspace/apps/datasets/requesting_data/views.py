from formtools.preview import FormPreview
from formtools.wizard.views import NamedUrlSessionWizardView

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.datasets.models import RequestingDataset
from dataworkspace.apps.datasets.requesting_data.forms import DatasetOwnersForm, DatasetNameForm, DatasetDescriptionsForm, DatasetDataOriginForm, DatasetPreviouslyPublishedForm


class RequestingDataWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ('name', DatasetNameForm),
        ('descriptions', DatasetDescriptionsForm),
        ('origin', DatasetDataOriginForm),
        ('owners', DatasetOwnersForm),
        # ('existing-system', DatasetExistingSystemForm),
        # ('published', DatasetPreviouslyPublishedForm),
        # ('licence', DatasetLicenceForm),
        # ('restrictions', DatasetRestrictionsForm),
        # ('purpose', DatasetPurposeForm),
        # ('usage', DatasetUsageForm),
        # ('security-classification', DatasetSecurityClassificationForm),
        # ('personal-data', DatasetPersonalDataForm),
        # ('special-personal-data', DatasetSpecialPersonalDataForm),
        # ('commercial-sensitive', DatasetCommercialSensitiveForm),
        # ('retention-period', DatasetRetentionPeriodForm),
        # ('update-frequency', DatasetUpdateFrequencyForm),
        # ('current-access', DatasetCurrentAccessForm),
        # ('intended-access', DatasetIntendedAccessForm),
        # ('location-restrictions', DatasetLocationRestrictionsForm),
        # ('security-clearance', DatasetSecurityClearanceForm),
        # ('network-restrictions', DatasetNetworkRestrictionsForm),
        # ('user-restrictions', DatasetUserRestrictionsForm),
    ]

    def get_template_names(self):
        return "datasets/requesting_data/summary_information.html"

    def done(self, form_list, **kwargs):

        notes_fields = ["origin", "existing-system", "published", "usage", "purpose",
                        "special-personal-data", "commercial-sensitive", "update-frequency",
                        "current-access", "intended-access", "location-restrictions",
                        "network-restrictions", "security-clearance", "user-restrictions"]

        requesting_dataset = RequestingDataset.objects.create(name=form_list[0].cleaned_data.get("name"))
        requesting_dataset.save()

        for form in form_list:
            for field in form.cleaned_data:
                if field in notes_fields:
                    requesting_dataset.notes = f"{form[field].label} {form.cleaned_data.get(field)}\n"
                    requesting_dataset.save()
                else:
                    setattr(requesting_dataset, field, form.cleaned_data.get(field))
                requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )
