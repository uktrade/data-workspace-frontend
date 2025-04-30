from django import forms
from django.contrib.auth import get_user_model
from django.forms import ValidationError

from dataworkspace.apps.datasets.models import RequestingDataset, SensitivityType
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemTextareaField,
)

from dataworkspace.apps.core.forms import ConditionalSupportTypeRadioWidget


class DatasetNameForm(GOVUKDesignSystemForm):
    name = GOVUKDesignSystemCharField(
        label="What is the name of the dataset?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )


class DatasetDescriptionsForm(GOVUKDesignSystemForm):
    short_description = GOVUKDesignSystemTextareaField(
        label="Summarise this dataset",
        help_text="Please provide a brief description of what it contains.",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    description = GOVUKDesignSystemTextareaField(
        label="Describe this dataset",
        help_text="This must contain enough detail to ensure non - experts can understand it's contents. Minimum 30 words.",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        description = cleaned_data["description"]
        if len(description.split(" ")) < 30:
            raise ValidationError("The description must be minimum 30 words")
        else:
            return cleaned_data


class DatasetInformationAssetOwnerForm(forms.Form):
    information_asset_owner = GOVUKDesignSystemTextareaField(
        label="Name of Information Asset Owner (IAO)",
        help_text="IAOs are senior civil servants accountable for information in their business area and associated risks.",
        required=True,
        error_messages={"required": "You must provide a search term."},
    )

    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        user_id = cleaned_data["information_asset_owner"]
        cleaned_data["information_asset_owner"] = User.objects.get(id=user_id)
        return cleaned_data


class DatasetInformationAssetManagerForm(forms.Form):
    information_asset_manager = forms.CharField(
        required=True,
        label="Name of Information Asset Manager (IAM)",
        help_text="IAMs have responsibility for managing the data, access requests and any changes.",
    )

    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        user_id = cleaned_data["information_asset_manager"]
        cleaned_data["information_asset_manager"] = User.objects.get(id=user_id)
        return cleaned_data


class DatasetEnquiriesContactForm(forms.Form):
    enquiries_contact = forms.CharField(
        required=True,
        label="Contact person",
        help_text="They should be the person who can best answer questions about the data. If anyone uses the ‘Report an issue’ link on a catalogue page they will get an email.",  # pylint: disable=line-too-long
    )

    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        user_id = cleaned_data["enquiries_contact"]
        cleaned_data["enquiries_contact"] = User.objects.get(id=user_id)
        return cleaned_data


class DatasetLicenceForm(GOVUKDesignSystemForm):
    licence_required = forms.CharField(
        label="Do you need/have a licence for this data?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    licence = GOVUKDesignSystemCharField(
        label="What licence do you have for this data?",
        required=False,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        licence_required = cleaned_data.get("licence_required", None)
        if licence_required == "yes" and cleaned_data["licence"] == "":
            raise ValidationError("Please enter a URL")
        return cleaned_data


class DatasetSecurityClassificationForm(GOVUKDesignSystemModelForm):
    sensitivity = forms.ModelMultipleChoiceField(
        queryset=SensitivityType.objects.all(), widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = RequestingDataset
        fields = [
            "government_security_classification",
            "sensitivity",
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data["government_security_classification"] is None:
            raise ValidationError("Please select a classification.")


class DatasetPersonalDataForm(GOVUKDesignSystemForm):
    personal_data_required = forms.CharField(
        label="Does it contain personal data?",
        help_text="Personal data means any information relating to an identified or identifiable living individual.\n"
        "“Identifiable living individual” means a living individual who can be identified, directly or indirectly, in particular by reference to either: \n"  # pylint: disable=line-too-long
        "An identifier such as a name, an identification number, location data or an online identifier \n"
        "One or more factors specific to the physical, physiological, genetic, mental, economic, cultural or social identity of the individual.",  # pylint: disable=line-too-long
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    personal_data = GOVUKDesignSystemCharField(
        label="What personal data does it contain?",
        required=False,
        help_text="Personal data means any information relating to an identified or identifiable living individual. “Identifiable living individual” means a living individual who can be identified, directly or indirectly, in particular by reference to - (a) an identifier such as a name, an identification number, location data or an online identifier, or (b) one or more factors specific to the physical, physiological, genetic, mental, economic, cultural or social identity of the individual.",  # pylint: disable=line-too-long
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        personal_data_required = cleaned_data.get("personal_data_required", None)
        if personal_data_required == "yes" and cleaned_data["personal_data"] == "":
            raise ValidationError("Please enter what personal data it contains")
        return cleaned_data


class DatasetSpecialPersonalDataForm(GOVUKDesignSystemForm):
    special_personal_data_required = forms.CharField(
        label="Does it contain special category personal data?",
        help_text="Special category data is personal data which the GDPR says is more sensitive, and so needs more protection.",  # pylint: disable=line-too-long
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    special_personal_data = GOVUKDesignSystemCharField(
        label="Does it contain special category personal data?",
        required=False,
        help_text="Special category data is personal data which the GDPR says is more sensitive, and so needs more protection.",  # pylint: disable=line-too-long
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        special_personal_data_required = cleaned_data.get("special_personal_data_required", None)
        if special_personal_data_required == "yes" and cleaned_data["special_personal_data"] == "":
            raise ValidationError("Please enter what special category personal data it contains")
        return cleaned_data


class DatasetRetentionPeriodForm(GOVUKDesignSystemForm):
    retention_policy = GOVUKDesignSystemCharField(
        label="What is the retention period? (Optional)",
        required=False,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )


class DatasetUpdateFrequencyForm(GOVUKDesignSystemForm):
    update_frequency = GOVUKDesignSystemRadioField(
        label="How often is the source data updated?",
        choices=[
            ("constant", "Constant"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("other", "Other"),
        ],
        widget=ConditionalSupportTypeRadioWidget(heading="h2"),
        error_messages={"required": "Please select how often the data is updated."},
    )
    message = GOVUKDesignSystemTextareaField(
        required=False,
        label="Tell us how often the source data is updated.",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 5},
        ),
    )


class DatasetIntendedAccessForm(GOVUKDesignSystemForm):
    intended_access = GOVUKDesignSystemRadioField(
        required=True,
        choices=[("yes", "Yes"), ("no", "No")],
        label="Should access on Data Workspace be open to all users by request?",
        widget=GOVUKDesignSystemRadiosWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
        ),
    )

    operational_impact = GOVUKDesignSystemTextareaField(
        label="Will this change of access have any operational impact?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetUserRestrictionsForm(GOVUKDesignSystemForm):
    user_restrictions_required = forms.CharField(
        label="Should access be restricted to certain user types?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    user_restrictions = GOVUKDesignSystemCharField(
        label="Which user types?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        user_restrictions_required = cleaned_data.get("user_restrictions_required", None)
        if user_restrictions_required == "yes" and cleaned_data["user_restrictions"] == "":
            raise ValidationError("Please provide information on the user restrictions")
        return cleaned_data


class SummaryPageForm(GOVUKDesignSystemForm):
    summary = forms.CharField(widget=forms.HiddenInput(), label="summary", required=False)


class TrackerPageForm(forms.Form):
    requesting_dataset = forms.CharField(
        required=True,
    )
