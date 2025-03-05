from django.contrib.auth import get_user_model
from django.forms import ValidationError


from dataworkspace.apps.datasets.models import RequestingDataset
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
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


class DatasetDataOriginForm(GOVUKDesignSystemForm):

    origin = GOVUKDesignSystemCharField(
        label="What type of dataset is this?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )


class DatasetOwnersForm(GOVUKDesignSystemForm):

    information_asset_owner = GOVUKDesignSystemCharField(
        label="Name of Information Asset Owner",
        help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
    )

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

    def clean(self):
        cleaned_data = super().clean()
        User = get_user_model()

        iao_first_name = cleaned_data.get("information_asset_owner").split(" ")[0].capitalize()
        iao_last_name = cleaned_data.get("information_asset_owner").split(" ")[1].capitalize()
        try:
            iao_user = User.objects.get(first_name=iao_first_name, last_name=iao_last_name)
            cleaned_data["information_asset_owner"] = iao_user
        except:
            raise ValidationError("This is not a real user")

        iam_first_name = cleaned_data.get("information_asset_manager").split(" ")[0].capitalize()
        iam_last_name = cleaned_data.get("information_asset_manager").split(" ")[1].capitalize()
        try:
            iam_user = User.objects.get(first_name=iam_first_name, last_name=iam_last_name)
            cleaned_data["information_asset_manager"] = iam_user
        except:
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
        except:
            raise ValidationError("This is not a real user")

        return cleaned_data


class DatasetSystemForm(GOVUKDesignSystemForm):

    name = GOVUKDesignSystemCharField(
        label="Which system is the data set currently stored on?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_is_heading=True),
        error_messages={"required": "Enter a table name"},
    )


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


class DatasetPreviouslyPublishedForm(GOVUKDesignSystemForm):

    previously_published = GOVUKDesignSystemCharField(
        label="Enter the URL of where it's currently published",
        required=False,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
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


class DatasetPurposeForm(GOVUKDesignSystemForm):

    purpose = GOVUKDesignSystemTextareaField(
        label="What purpose has the data been collected for?",
        required=True,
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
        label="What will the data be used for on Data Workspace?",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetCurrentAccessForm(GOVUKDesignSystemForm):

    usage = GOVUKDesignSystemTextareaField(
        label="Who currently has access to this dataset?",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DatasetCurrentAccessForm(GOVUKDesignSystemForm):

    current_access = GOVUKDesignSystemTextareaField(
        label="Who currently has access to this dataset?",
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


class DatasetSecurityClearanceForm(GOVUKDesignSystemForm):

    security_clearance = GOVUKDesignSystemRadioField(
        required=True,
        choices=[
            ("BPSS", "Basic level of security clearance(BPSS)"),
            ("CTC", "Counter Terrorist Check"),
            ("SC", "Security Check"),
            ("DV", "Developed Vetting"),
        ],
        label="What level of security clearance should be required to access this data?",
        help_text="All people who work for/in the Civil Service need to have a basic level of security clearance BPSS",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
    )


class DatasetNetworkRestrictionsForm(GOVUKDesignSystemForm):

    network_restrictions = GOVUKDesignSystemTextareaField(
        label="Should access be limited based on device types and networks?",
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

    user_restrictions = GOVUKDesignSystemTextareaField(
        label="Should access be trstricted to certain users types?",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
    )


class DaatasetSecurityClassificationForm(GOVUKDesignSystemModelForm):

    class Meta:
        model = RequestingDataset
        fields = [
            "government_security_classification",
            "sensitivity",
        ]
    # sensitivity = GOVUKDesignSystemRadioField(
    #     required=False,
    #     label="What would you like to do?",
    #     choices=SecurityClassificationTypes.choices,
    #     widget=ConditionalSupportTypeRadioWidget(heading="h2", attrs={'data-type', 'sensitivity'}),
    # )
