from dataworkspace.forms import (
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
)


class TableSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemRadioField(
            required=False,
            label="Select an existing schema from this catalogue page",
            widget=GOVUKDesignSystemRadiosWidget(heading="h2", extra_label_classes="govuk-heading-m"),
            error_messages={"required": "You must select a schema."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(self)
        # schema_choices = user_choice + team_choices + all_choices
        # self.fields["schema"].choices = schema_choices