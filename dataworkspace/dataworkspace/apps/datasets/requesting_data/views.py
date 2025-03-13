from formtools.preview import FormPreview
from formtools.wizard.views import NamedUrlSessionWizardView

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView
import waffle

from dataworkspace.apps.datasets.models import RequestingDataset
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetCommercialSensitiveForm,
    DatasetOwnersForm,
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
    DatasetRetentionPeriodForm,
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetUpdateFrequencyForm,
)
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

from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
)
from dataworkspace.apps.datasets.models import (
    RequestingDataset,
)
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
    DatasetPersonalDataForm,
)
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
)
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetDataOriginForm,
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

    # if waffle.flag_is_active(request, settings.REQUESTING_DATA)


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
                if field == "sensitivity":
                    requesting_dataset.sensitivity.set(form.cleaned_data.get("sensitivity"))
                else:
                    setattr(requesting_dataset, field, form.cleaned_data.get(field))
                requesting_dataset.save()

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )
