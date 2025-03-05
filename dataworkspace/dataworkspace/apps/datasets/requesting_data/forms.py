import re

from django import forms
from django.core.validators import FileExtensionValidator
from django.forms import ValidationError

from dataworkspace.apps.core.forms import ConditionalSupportTypeRadioWidget
from dataworkspace.apps.core.storage import malware_file_validator
from dataworkspace.apps.core.utils import get_postgres_datatype_choices
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemSelectWidget,
    GOVUKDesignSystemTextCharCountWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
)


class DatasetNameForm(GOVUKDesignSystemForm):

    name = GOVUKDesignSystemCharField(
        label="What is the name of the dataset?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_is_heading=True),
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

    data_origin = GOVUKDesignSystemCharField(
        label="What type of dataset is this?",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_is_heading=True),
    )


class DataSetOwnersForm(GOVUKDesignSystemForm):

    information_asset_owner = GOVUKDesignSystemCharField(
        label="Name of Information Asset Owner",
        help_text="IAO's are responsible for ensuring information assets are handled and managed appropriately",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_is_heading=True),
    )

