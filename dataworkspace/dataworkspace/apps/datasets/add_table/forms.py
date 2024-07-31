from dataworkspace.forms import (
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
)


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
