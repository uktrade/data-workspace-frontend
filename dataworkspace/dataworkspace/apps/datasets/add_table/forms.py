from dataworkspace.forms import GOVUKDesignSystemForm, GOVUKDesignSystemRadioField, GOVUKDesignSystemRadiosWidget


class TableSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemRadioField(
        required=False,
        label="Select an existing schema from this catalogue page",
        choices=['public', 'dbt'],
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
        ),