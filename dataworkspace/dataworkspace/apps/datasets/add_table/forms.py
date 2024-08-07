from django.forms import ValidationError

from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
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
        label="Descriptive Name",
        required=True,
        help_text="It should not contain the words 'record', 'data' or 'dataset'. It should also not contain underscores. For example, Companies in India.",  # pylint: disable=line-too-long
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False),
        error_messages={"required": "Enter a descriptive name"},
    )
