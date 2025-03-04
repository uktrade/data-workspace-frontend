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

    title = "Summary information"

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
        error_messages={"required": "Enter a table name"},
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
        error_messages={"required": "Enter a table name"},
    )

    title = "Summary information"


class DatasetRestrictionsForm(GOVUKDesignSystemForm):

    restrictions_on_usage = GOVUKDesignSystemRadioField(
        label="What type of dataset is this?",
        choices=[
            (t, t.label)
            for t in [DataSetType.MASTER, DataSetType.DATACUT, DataSetType.REFERENCE]
        ],
        widget=ConditionalSupportTypeRadioWidget(heading="h2"),
    )

    title = "Summary information"


class TableNameForm(GOVUKDesignSystemForm):
    table_name = GOVUKDesignSystemCharField(
        label="Enter your table name",
        required=True,
        help_text="Your table name needs to be unique, have less than 42 characters and not contain any special characters apart from underscores.",  # pylint: disable=line-too-long
        error_messages={"required": "Enter a table name"},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kwargs = kwargs.pop("initial")
        schema = kwargs["schema"] + "."
        descriptive_name = kwargs["descriptive_name"].replace(" ", "_").lower()
        self.table_names = kwargs["table_names"]
        self.fields["table_name"].widget = GOVUKDesignSystemTextCharCountWidget(
            prefix=schema,
            character_limit="42",
        )
        self.fields["table_name"].widget.attrs.update(
            {
                "label": self.fields["table_name"].label,
                "help_text": self.fields["table_name"].help_text,
            }
        )

        self.fields["table_name"].initial = descriptive_name

    def clean_table_name(self):
        cleaned_data = super().clean()
        table_name = str(cleaned_data["table_name"])
        if len(table_name) > 42:
            raise ValidationError("Table name must be 42 characters or less")
        elif bool(re.search(r"[^A-Za-z0-9_]", table_name)):
            raise ValidationError("Table name cannot contain special characters")
        elif table_name in self.table_names:
            raise ValidationError("Table name already in use")
        elif "dataset" in table_name:
            raise ValidationError("Table name cannot contain the word 'dataset'")
        elif "data" in table_name:
            raise ValidationError("Table name cannot contain the word 'data'")
        elif "record" in table_name:
            raise ValidationError("Table name cannot contain the word 'record'")
        return table_name
