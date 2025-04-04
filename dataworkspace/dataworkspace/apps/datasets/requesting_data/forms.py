from django import forms
from django.contrib.auth import get_user_model
from django.forms import ValidationError


from dataworkspace.apps.datasets.models import RequestingDataset, SensitivityType
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemDateField,
    GOVUKDesignSystemDateWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemTextCharCountWidget,
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
        help_text="Please ensure this contains enough detail to ensure non-experts viewing the Data Workspace catalogue can understand it's contents. Minimum 30 words",  # pylint: disable=line-too-long
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetDataOriginForm(GOVUKDesignSystemForm):
    origin = GOVUKDesignSystemCharField(
        label="Where does the data come from?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )


class DatasetInformationAssetOwnerForm(forms.Form):
    information_asset_owner = forms.CharField(
        required=True,
        label="Name of information Asset Owner (IAO)",
        help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately"
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
        label="Name of information Asset Manager (IAM)",
        help_text="IAM's have knowledge and duties associated with an asset and so often support the IAO"
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
        help_text="Description of contact person"
    )

    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        user_id = cleaned_data["enquiries_contact"]
        cleaned_data["enquiries_contact"] = User.objects.get(id=user_id)
        return cleaned_data


class DatasetExistingSystemForm(GOVUKDesignSystemForm):
    existing_system = GOVUKDesignSystemTextareaField(
        label="Which system is the data set currently stored on?",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetLicenceForm(GOVUKDesignSystemForm):
    licence_required = forms.CharField(
        label="Do you need/have a licence for this data?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
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
        if licence_required == "yes" and cleaned_data["licence"] ==  "":
            raise ValidationError("Please enter a URL")
        return cleaned_data


class DatasetRestrictionsForm(GOVUKDesignSystemForm):
    restrictions = GOVUKDesignSystemTextareaField(
        label="What are the usage restrictions?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetUsageForm(GOVUKDesignSystemForm):
    usage_required = forms.CharField(
        label="Are there any restrictions on usage?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    usage = GOVUKDesignSystemCharField(
        label="What will the data be used for on Data Workspace?",
        required=False,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        usage_required = cleaned_data.get("usage_required", None)
        if usage_required == "yes" and cleaned_data["usage"] ==  "":
            raise ValidationError("Please enter the usage restrictions")
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
        if personal_data_required == "yes" and cleaned_data["personal_data"] ==  "":
            raise ValidationError("Please enter what personal data it contains")
        return cleaned_data


class DatasetSpecialPersonalDataForm(GOVUKDesignSystemForm):
    special_personal_data_required = forms.CharField(
        label="Does it contain special category personal data?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    special_personal_data = GOVUKDesignSystemCharField(
        label="Does it contain special category personal data?",
        required=False,
        help_text="Special category data is personal data which the GDPR says is more sensitive, and so needs more protection.",
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
        if special_personal_data_required == "yes" and cleaned_data["special_personal_data"] ==  "":
            raise ValidationError("Please enter what special category personal data it contains")
        return cleaned_data


class DatasetCommercialSensitiveForm(GOVUKDesignSystemForm):
    commercial_sensitive_required = forms.CharField(
        label="Does it contain special category personal data?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    commercial_sensitive = GOVUKDesignSystemCharField(
        label="What commercially sensitive data does it contain?",
        required=False,
        help_text="Commercially sensitive information is information that if disclosed, could prejudice a supplier's commercial interests e.g. trade secrets, profit margins or new ideas. This type of information is protected through Confidentiality Agreements.",
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
        commercial_sensitive_required = cleaned_data.get("commercial_sensitive_required", None)
        if commercial_sensitive_required == "yes" and cleaned_data["commercial_sensitive"] ==  "":
            raise ValidationError("Please enter what commercially sensitive data it contains")
        return cleaned_data


class DatasetRetentionPeriodForm(GOVUKDesignSystemForm):
    retention_policy = GOVUKDesignSystemCharField(
        label="What is the retention period?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
        error_messages={"required": "Enter a retention period."},
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
        label="Should access on Data Workspace be open to all users on request?",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
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


class DatasetLocationRestrictionsForm(GOVUKDesignSystemForm):
    location_restrictions_required = forms.CharField(
        label="Should there be any location restrictions for access to this data set?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    location_restrictions = GOVUKDesignSystemCharField(
        label="Provide brief information about this",
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
        location_restrictions_required = cleaned_data.get("location_restrictions_required", None)
        if location_restrictions_required == "yes" and cleaned_data["location_restrictions"] ==  "":
            raise ValidationError("Please provide information on the location restrictions")
        return cleaned_data


class DatasetNetworkRestrictionsForm(GOVUKDesignSystemForm):
    network_restrictions_required = forms.CharField(
        label="Should access be limited based on device types and networks?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(),
    )

    network_restrictions = GOVUKDesignSystemCharField(
        label="Please provide some brief information about this",
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
        network_restrictions_required = cleaned_data.get("network_restrictions_required", None)
        if network_restrictions_required == "yes" and cleaned_data["network_restrictions"] ==  "":
            raise ValidationError("Please provide information on the network restrictions")
        return cleaned_data


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
        if user_restrictions_required == "yes" and cleaned_data["user_restrictions"] ==  "":
            raise ValidationError("Please provide information on the user restrictions")
        return cleaned_data


class SummaryPageForm(GOVUKDesignSystemForm):
    summary = forms.CharField(widget=forms.HiddenInput(), label="summary", required=False)


class TrackerPageForm(forms.Form):
    requesting_dataset = forms.CharField(
        required=True,
    )
