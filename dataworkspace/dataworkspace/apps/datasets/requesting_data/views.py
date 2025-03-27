import re
from django import forms
from django.forms import model_to_dict
from django.shortcuts import get_object_or_404
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
    DatasetEnquiriesContactForm,
    DatasetInformationAssetManagerForm,
    DatasetInformationAssetOwnerForm,
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

    def get_template_names(self):
        user_search_pages = [
            "information-asset-owner",
            "information-asset-manager",
            "enquiries-contact",
        ]
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        if self.steps.current == "update-frequency":
            return "datasets/requesting_data/update_frequency_options.html"
        if self.steps.current in user_search_pages:
            return "datasets/requesting_data/user_search.html"
        else:
            return "datasets/requesting_data/summary_information.html"

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
        if self.steps.current == "information-asset-owner":
            context["form_page"] = "information-asset-owner"
            context["field"] = "information_asset_owner"
            context["label"] = "Name of Information Asset Owner"
            context["help_text"] = (
                "IAO's are responsible for ensuring information assets are handled and managed appropriately"
            )
            try:
                search_query = self.request.GET.dict()["search"]
                context["search_query"] = search_query
                if search_query:
                    context["search_results"] = self.get_users(search_query=search_query)
            except:
                return context
        elif self.steps.current == "information-asset-manager":
            context["form_page"] = "information-asset-manager"
            context["field"] = "information_asset_manager"
            context["label"] = "Name of Information Asset Manager"
            context["help_text"] = (
                "IAM's ahve knowledge and duties associated with an asset, and so often support the IAO"
            )
            try:
                search_query = self.request.GET.dict()["search"]
                context["search_query"] = search_query
                if search_query:
                    context["search_results"] = self.get_users(search_query=search_query)
            except:
                return context
        elif self.steps.current == "enquiries-contact":
            context["form_page"] = "enquiries-contact"
            context["field"] = "enquiries_contact"
            context["label"] = "Contact person"
            context["help_text"] = "Description of contact person"
            try:
                search_query = self.request.GET.dict()["search"]
                context["search_query"] = search_query
                if search_query:
                    context["search_results"] = self.get_users(search_query=search_query)
            except:
                return context

        # could be abstracted
        if self.steps.current == "summary":

            # the feild label in the forms
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

            for name, form in self.form_list.items():
                for name, field in form.base_fields.items():
                    question = field.label
                    questions[name] = question
            for step in self.storage.data["step_data"]:
                for key, value in self.get_cleaned_data_for_step(step).items():

                    if key in section_one_fields:
                        section.append(
                            {
                                step: {"question": questions[key], "answer": value},
                            },
                        )

            context["summary"] = section
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
            return "datasets/requesting_data/summary_information.html"

    def done(self, form_list, **kwargs):

        notes_fields = [
            "origin",
            "existing_system",
            "previously_published",
            "usage",
        ]

        # these fields need to added to notes as they no do have fields themselves but are useful to analysts.

        requesting_dataset = RequestingDataset.objects.create(
            name=form_list[0].cleaned_data.get("name")
        )
        requesting_dataset.save()

        # DatasetUsageForm to be sent to restrictions on usage.
        add_fields(form_list, requesting_dataset, notes_fields)
        requesting_dataset.stage_one_complete = True
        requesting_dataset.save()
        self.request.session["requesting_dataset"] = requesting_dataset.id
        return HttpResponseRedirect(
            reverse("requesting-data-about-this-data-step", args={("security-classification")})
        )


class RequestingDataAboutThisDataWizardView(NamedUrlSessionWizardView, FormPreview):
    def get_template_names(self):

        if self.steps.current == "summary":
            return "datasets/requesting_data/summary.html"
        if self.steps.current == "security-classification":
            return "datasets/requesting_data/security.html"
        else:
            return "datasets/requesting_data/about_the_data.html"

    form_list = [
        ("security-classification", DatasetSecurityClassificationForm),
        ("personal-data", DatasetPersonalDataForm),
        ("special-personal-data", DatasetSpecialPersonalDataForm),
        ("commercial-sensitive", DatasetCommercialSensitiveForm),
        ("retention-period", DatasetRetentionPeriodForm),
        ("update-frequency", DatasetUpdateFrequencyForm),
        ("summary", SummaryPageForm),
    ]

    # def get_form_kwargs(self, step=None):
    #     kwargs = super().get_form_kwargs(step)
    #     requesting_dataset_id = self.request.session.get("requesting_dataset")
    #     requesting_dataset = get_object_or_404(RequestingDataset, id=requesting_dataset_id)

    #     if requesting_dataset_id:
    #         form_class = self.form_list[step]
    #         if issubclass(form_class, forms.ModelForm):
    #             kwargs["instance"] = requesting_dataset
    #         else:
    #             kwargs["initial"] = {'requesting_dataset_id': requesting_dataset.id}
    #     print("KWARGS IN GET KWARGS: ", kwargs)
    #     return kwargs

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "summary":
            # the feild label in the forms
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

            for name, form in self.form_list.items():
                for name, field in form.base_fields.items():
                    question = field.label
                    questions[name] = question
            for step in self.storage.data["step_data"]:
                for key, value in self.get_cleaned_data_for_step(step).items():
                    if key in section_two_fields:
                        section.append(
                            {
                                step: {"question": questions[key], "answer": value},
                            },
                        )

            context["summary"] = section
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

        # these fields need to added to notes as they no do have fields themselves but are useful to analysts.
        User = get_user_model()

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

        return HttpResponseRedirect(
            reverse(
                "datasets:find_datasets",
            )
        )


class RequestingDataAccessRestrictionsWizardView(NamedUrlSessionWizardView, FormPreview):

    form_list = [
        ("intended-access", DatasetIntendedAccessForm),
        ("location-restrictions", DatasetLocationRestrictionsForm),
        ("network-restrictions", DatasetNetworkRestrictionsForm),
        ("user-restrictions", DatasetUserRestrictionsForm),
        ("summary", SummaryPageForm),
    ]
