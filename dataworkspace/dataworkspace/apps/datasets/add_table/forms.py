import re
from django.forms import ValidationError
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextCharCountWidget,
)


class TableSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemRadioField(
        required=True,
        label="Select a schema for your table",
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", label_size="l"),
        error_messages={"required": "Select a schema"},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "schema_choices" in kwargs.get("initial", {}):
            self.fields["schema"].choices = kwargs.pop("initial")["schema_choices"]


class DescriptiveNameForm(GOVUKDesignSystemForm):

    def clean_descriptive_name(self):
        cleaned_data = super().clean()
        descriptive_name = cleaned_data["descriptive_name"].lower()
        words = ["record", "dataset", "data"]
        for word in words:
            if word in descriptive_name:
                raise ValidationError(f"Descriptive name cannot contain the word '{word}'")
        if "_" in descriptive_name:
            raise ValidationError("Descriptive name cannot contain underscores")
        return descriptive_name

    descriptive_name = GOVUKDesignSystemCharField(
        label="Enter a descriptive name for your table",
        required=True,
        help_text="It should not contain the words 'record', 'data' or 'dataset'. It should also not contain underscores. For example, Companies in India.",  # pylint: disable=line-too-long
        widget=GOVUKDesignSystemTextWidget(label_is_heading=True, label_size="l"),
        error_messages={"required": "Enter a descriptive name"},
    )


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
        descriptive_name = kwargs["descriptive_name"].replace(" ", "_")
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
        elif bool(re.search(r"[^A-Za-z_]", table_name)):
            raise ValidationError("Table name cannot contain numbers or special characters")
        elif table_name in self.table_names:
            raise ValidationError("Table name already in use")
        elif "dataset" in table_name:
            raise ValidationError("Table name cannot contain the word 'dataset'")
        elif "data" in table_name:
            raise ValidationError("Table name cannot contain the word 'data'")
        elif "record" in table_name:
            raise ValidationError("Table name cannot contain the word 'record'")
        return table_name
