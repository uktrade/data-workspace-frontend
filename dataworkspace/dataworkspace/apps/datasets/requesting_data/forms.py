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
        help_text="Please ensure this contains enough detail to ensure non-experts viewing the Data Workspace catalogue can understand it's contents. Minimum 30 words",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    # def clean(self):
    #     cleaned_data = super().clean()
    #     if len(cleaned_data['description']) < 30:
    #         raise ValidationError('Description must have at minimum 30 words.')


class DatasetDataOriginForm(GOVUKDesignSystemForm):

    origin = GOVUKDesignSystemCharField(
        label="Where does the data come from?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        print('HELLO IM IN THE CLEANED DATA')
        print(cleaned_data)
        return cleaned_data

class DatasetIAOForm(forms.Form):
    

    # information_asset_owner = GOVUKDesignSystemCharField(
    #     label="Name of Information Asset Owner",
    #     help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately",
    #     required=True,
    #     widget=GOVUKDesignSystemTextWidget(
    #         label_is_heading=True,
    #         label_size="m",
    #     ),
    # )


    def clean(self):
        User = get_user_model()
        cleaned_data = super().clean()
        print('HELLO IM IN THE CLEANED DATA')
        cleaned_data["information_asset_owner"] = User.objects.get(first_name="Vyvyan")
        print(cleaned_data)
        return cleaned_data


class DatasetOwnersForm(GOVUKDesignSystemForm):

    # information_asset_owner = GOVUKDesignSystemCharField(
    #     label="Name of Information Asset Owner",
    #     help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately",
    #     required=True,
    #     widget=GOVUKDesignSystemTextWidget(
    #         label_is_heading=True,
    #         label_size="m",
    #     ),
    # )

    information_asset_manager = GOVUKDesignSystemCharField(
        label="Name of Information Asset Manager",
        help_text="IAM's have knowledge and duties associated with an asset, and so often support the IAO",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    enquiries_contact = GOVUKDesignSystemCharField(
        label="Contact person",
        help_text="Description of contact person",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

    # iao2 = GOVUKDesignSystemTextareaField(
    #     label="Enter one or more email addresses on separate lines or search for a single user by name.",
    #     widget=GOVUKDesignSystemTextareaWidget(
    #         label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
    #     ),
    #     error_messages={"required": "You must provide a search term."},
    # )

    def clean(self):
        cleaned_data = super().clean()
        User = get_user_model()

        iao_first_name = cleaned_data.get("information_asset_owner").split(" ")[0].capitalize()
        iao_last_name = cleaned_data.get("information_asset_owner").split(" ")[1].capitalize()
        try:
            iao_user = User.objects.get(first_name=iao_first_name, last_name=iao_last_name)
            cleaned_data["information_asset_owner"] = iao_user
        except Exception:
            raise ValidationError("This is not a real user")

        iam_first_name = cleaned_data.get("information_asset_manager").split(" ")[0].capitalize()
        iam_last_name = cleaned_data.get("information_asset_manager").split(" ")[1].capitalize()
        try:
            iam_user = User.objects.get(first_name=iam_first_name, last_name=iam_last_name)
            cleaned_data["information_asset_manager"] = iam_user

        except Exception:
            raise ValidationError("This is not a real user")

        enquiries_contact_first_name = (
            cleaned_data.get("enquiries_contact").split(" ")[0].capitalize()
        )
        enquiries_contact_last_name = (
            cleaned_data.get("enquiries_contact").split(" ")[1].capitalize()
        )
        try:
            enquiries_contact_user = User.objects.get(
                first_name=enquiries_contact_first_name, last_name=enquiries_contact_last_name
            )
            cleaned_data["enquiries_contact"] = enquiries_contact_user

        except Exception:
            raise ValidationError("This is not a real user")

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

    licence = GOVUKDesignSystemCharField(
        label="What licence do you have for this data?",
        required=False,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )


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

    usage = GOVUKDesignSystemTextareaField(
        label="How can this data be used on Data Workspace?",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
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

    location_restrictions = GOVUKDesignSystemTextareaField(
        label="Should there be any location restrictions for access to this data set?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetNetworkRestrictionsForm(GOVUKDesignSystemForm):
    # condicitonal radio buttons
    network_restrictions = GOVUKDesignSystemTextareaField(
        label="Should access be limited based on device types and networks?",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetUserRestrictionsForm(GOVUKDesignSystemForm):
    # change to a radio conditionaly button at some point in the near future
    user_restrictions = GOVUKDesignSystemTextareaField(
        label="Should access be restricted to certain users types?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


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
        if cleaned_data['government_security_classification'] == None :
            raise ValidationError('Please select a classification.')


class DatasetPersonalDataForm(GOVUKDesignSystemForm):

    personal_data = GOVUKDesignSystemTextareaField(
        required=False,
        label="Does it contain personal data?",
        help_text="Personal data means any information relating to an identified or identifiable living individual. “Identifiable living individual” means a living individual who can be identified, directly or indirectly, in particular by reference to - (a) an identifier such as a name, an identification number, location data or an online identifier, or (b) one or more factors specific to the physical, physiological, genetic, mental, economic, cultural or social identity of the individual.",
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetSpecialPersonalDataForm(GOVUKDesignSystemForm):

    special_personal_data = GOVUKDesignSystemTextareaField(
        required=False,
        label="Does it contain special category personal data?",
        help_text="Special category data is personal data which the GDPR says is more sensitive, and so needs more protection.",
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetCommercialSensitiveForm(GOVUKDesignSystemForm):

    commercial_sensitive = GOVUKDesignSystemTextareaField(
        required=False,
        label="Does it contain commercially sensitive data?",
        help_text="Commercially sensitive information is information that if disclosed, could prejudice a supplier's commercial interests e.g. trade secrets, profit margins or new ideas. This type of information is protected through Confidentiality Agreements.",
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetRetentionPeriodForm(GOVUKDesignSystemForm):

    retention_policy = GOVUKDesignSystemCharField(
        label="What is the retention period?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
        error_messages={"required": "Enter a table name"},
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
        label="Tell us how we can help you",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 5},
        ),
    )
