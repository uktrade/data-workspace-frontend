from django.core.validators import FileExtensionValidator
from django import forms

from dataworkspace.apps.core.constants import SCHEMA_POSTGRES_DATA_TYPE_MAP
from dataworkspace.apps.core.storage import malware_file_validator
from dataworkspace.forms import (
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemSelectWidget,
)


class SourceTableUploadForm(GOVUKDesignSystemForm):
    csv_file = GOVUKDesignSystemFileField(
        required=True,
        label="Update with a new file",
        help_text="Upload a new CSV to this table",
        widget=GOVUKDesignSystemFileInputWidget(
            label_is_heading=True,
            heading="h2",
            heading_class="govuk-heading-s",
            extra_label_classes="govuk-!-font-weight-bold",
            show_selected_file=True,
            attrs={"accept": "text/csv"},
        ),
        validators=[
            FileExtensionValidator(allowed_extensions=["csv"]),
            malware_file_validator,
        ],
        error_messages={
            "required": "You must provide a CSV to upload.",
            "invalid_extension": "Invalid file type. Only CSV files are currently supported.",
        },
    )


class SourceTableUploadColumnConfigForm(GOVUKDesignSystemForm):
    path = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.column_definitions = kwargs.pop("column_definitions")
        if not self.column_definitions:
            raise ValueError("Definitions for at least one column must be provided")
        super().__init__(*args, **kwargs)

        for col_def in self.column_definitions:
            self.fields[col_def["column_name"]] = GOVUKDesignSystemChoiceField(
                label=col_def["column_name"],
                initial=col_def["data_type"],
                choices=(
                    (value, name.capitalize())
                    for name, value in SCHEMA_POSTGRES_DATA_TYPE_MAP.items()
                ),
                widget=GOVUKDesignSystemSelectWidget(
                    label_is_heading=False,
                    extra_label_classes="govuk-visually-hidden",
                ),
            )

    def get_data_type_fields(self):
        for col_def in self.column_definitions:
            yield self[col_def["column_name"]], ", ".join(map(str, col_def["sample_data"]))
