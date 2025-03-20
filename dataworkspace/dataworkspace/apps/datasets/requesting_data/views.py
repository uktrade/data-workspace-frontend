import re
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
    SummaryPageForm,
    TrackerPageForm
)


class RequestingDataWizardView(NamedUrlSessionWizardView, FormPreview):
    form_list = [
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("origin", DatasetDataOriginForm),
        # ("owners", DatasetOwnersForm),
        # ("existing-system", DatasetExistingSystemForm),
        # ("licence", DatasetLicenceForm),
        # ("restrictions", DatasetRestrictionsForm),
        # ("usage", DatasetUsageForm),
        ("summary", SummaryPageForm),
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
        ("summary", SummaryPageForm),

    ]

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
        else:
            return "datasets/requesting_data/summary_information.html"

    # def done(self, form_list, **kwargs):
    #     # these fields need to added to notes as they no do have fields themselves but are useful to analysts.
    #     User = get_user_model()

    #     data_dict = model_to_dict(
    #         requesting_dataset,
    #         exclude=["id", "tags", "user", "sensitivity", "data_catalogue_editors"],
    #     )
    #     data_dict["enquiries_contact"] = requesting_dataset.enquiries_contact
    #     data_dict["information_asset_manager"] = requesting_dataset.information_asset_manager
    #     data_dict["information_asset_owner"] = requesting_dataset.information_asset_owner
    #     data_dict["slug"] = requesting_dataset.name.lower().replace(" ", "-")

    #     dataset = DataSet.objects.create(**data_dict)
    #     dataset.data_catalogue_editors.set(requesting_dataset.data_catalogue_editors.all())
    #     dataset.sensitivity.set(requesting_dataset.sensitivity.all())

    #     # TODO delete the requesting_dataset object, leaving ofr now as useful in developement

    #     return HttpResponseRedirect(
    #         reverse(
    #             "datasets:find_datasets",
    #         )
    #     )

    def process_step(self, form):
        User = get_user_model()

        if self.steps.current == "summary":
            requesting_dataset = RequestingDataset.objects.create(
                name=self.form_list[0].cleaned_data.get("name")
            )

        # TODO DatasetUsageForm to be sent to restrictions on usage.

            for form in self.form_list:
                for field in form.cleaned_data:
                    if field in self.notes_fields and form.cleaned_data.get(field):
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

                requesting_dataset.save()
        return self.get_form_step_data(form)
        
        # TODO wipe session

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.steps.current == "summary":

            section_one_fields = ["name", "short_description", "description", "origin"]

            section = []
            questions = {}

            print(self.storage.data["step_data"])


            for name, form in self.form_list.items():
                for name, field in form.base_fields.items():
                    question = re.sub(r"[,\(\)']", "", field.label)
                    questions[name] = question
            for step in self.storage.data["step_data"]:
                print('HELLOOOOOOOOOOOOOOOOOO')
                print(step)
                print(type(step))
                for key, value in self.get_cleaned_data_for_step(step).items():
                    if key in section_one_fields:
                        section.append(
                            {step:
                                {
                                    "question": questions[key],
                                    "answer": value},
                            },)

            context["summary"] = section
        return context



