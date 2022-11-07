from dataworkspace.forms import (
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadiosWidget,
)


class SelectCollectionForMembershipForm(GOVUKDesignSystemForm):
    collection = GOVUKDesignSystemRadioField(
        required=True,
        label="Choose a collection you'll add the data to",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
    )

    def __init__(self, *args, **kwargs):
        self.user_collections = kwargs.pop("user_collections")
        super().__init__(*args, **kwargs)
        self.fields["collection"].choices = ((x.id, x.name) for x in self.user_collections)
