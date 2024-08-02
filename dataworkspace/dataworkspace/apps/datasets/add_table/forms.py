from xml.dom import ValidationErr
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
)
from django.forms import ValidationError


class TableSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemRadioField(
        required=True,
        label="Select an existing schema from this catalogue page",
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", extra_label_classes="govuk-heading-m"),
        error_messages={"required": "You must select a schema."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "schema_choices" in kwargs.get("initial", {}):
            self.fields["schema"].choices = kwargs.pop("initial")["schema_choices"]


class DescriptiveNameForm(GOVUKDesignSystemForm):

    def clean_descriptive_name(self):
        cleaned_data = super().clean()
        descriptive_name = cleaned_data["descriptive_name"].lower()
        if 'data' in descriptive_name:
            print('Descriptive name cannot contain the word ‘data’')
            raise ValidationError(
                "Descriptive name cannot contain the word ‘data’"
            )
        elif 'dataset' in descriptive_name:
            raise ValidationError(
                    "Descriptive name cannot contain the word ‘data’"
                )
        elif 'records' in descriptive_name:
            raise ValidationError(
                    "Descriptive name cannot contain the word ‘data’"
                )
        elif '_' in descriptive_name:
            raise ValidationError(
                    "Descriptive name cannot contain the word ‘data’"
                )
        return descriptive_name
    
    descriptive_name = GOVUKDesignSystemCharField(
        label="Descriptive Name",
        required=True,
        help_text="It should not contain the words ‘records’, ‘data’ or ‘dataset’. It should also not contain underscores. for example, Companies in India.",
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False),
        error_messages={"required": "Enter a descriptive name",
                        },
    )

