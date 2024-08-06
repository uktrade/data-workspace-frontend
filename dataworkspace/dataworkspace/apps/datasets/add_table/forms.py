from dataworkspace.forms import (
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
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
