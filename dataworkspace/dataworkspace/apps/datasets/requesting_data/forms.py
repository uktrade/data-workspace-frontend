from django.contrib.auth import get_user_model
from django.forms import ValidationError

from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
)


class DatasetNameForm(GOVUKDesignSystemForm):

    name = GOVUKDesignSystemCharField(
        label="What is the name of the dataset?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=True,
            label_size="m",
        ),
        error_messages={"required": "Enter a table name"},
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
        label="Name of Information Asset Owner",
        help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately",
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

        enquiries_contact_first_name = cleaned_data.get("enquiries_contact").split(" ")[0].capitalize()
        enquiries_contact_last_name = cleaned_data.get("enquiries_contact").split(" ")[1].capitalize()
        try:
            enquiries_contact_user = User.objects.get(first_name=enquiries_contact_first_name, last_name=enquiries_contact_last_name)
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
