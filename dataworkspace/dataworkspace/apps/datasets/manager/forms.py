from django.core.validators import FileExtensionValidator
from django import forms

from dataworkspace.apps.core.storage import malware_file_validator
from dataworkspace.apps.core.utils import get_postgres_datatype_choices
from dataworkspace.apps.core.forms import ConditionalSupportTypeRadioWidget
from dataworkspace.forms import (
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemSelectWidget,
    GOVUKDesignSystemRadioField,
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
    auto_generate_id_column = GOVUKDesignSystemRadioField(
        label="Do you want to generate an ID column?",
        help_text="This will add an ID column and assign an ID to each row in your table. \
        The ID will be an increasing integer, e.g. 1, 2, 3.",
        choices=[("True", "Yes"), ("False", "No")],
        widget=ConditionalSupportTypeRadioWidget(heading="h2", label_size="m", small=False),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.column_definitions = kwargs.pop("column_definitions")
        self.show_id_form = True

        if not self.column_definitions:
            raise ValueError("Definitions for at least one column must be provided")
        super().__init__(*args, **kwargs)

        for col_def in self.column_definitions:
            if col_def["column_name"] == "id":
                self.show_id_form = False
            self.fields[col_def["column_name"]] = GOVUKDesignSystemChoiceField(
                label=col_def["column_name"],
                initial=col_def["data_type"],
                choices=get_postgres_datatype_choices(),
                widget=GOVUKDesignSystemSelectWidget(
                    label_is_heading=False,
                    extra_label_classes="govuk-visually-hidden",
                ),
            )

    def get_data_type_fields(self):
        for col_def in self.column_definitions:
            yield self[col_def["column_name"]], ", ".join(map(str, col_def["sample_data"]))
