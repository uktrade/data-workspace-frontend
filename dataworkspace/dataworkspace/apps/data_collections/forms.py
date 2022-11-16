from django import forms

from dataworkspace.apps.data_collections.models import (
    CollectionDatasetMembership,
    CollectionUserMembership,
    CollectionVisualisationCatalogueItemMembership,
)
from dataworkspace.forms import (
    GOVUKDesignSystemEmailField,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
)


class SelectCollectionForMembershipForm(GOVUKDesignSystemForm):
    collection = GOVUKDesignSystemRadioField(
        required=False,
        label="Choose the collection you want to add this item to",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
    )

    def __init__(self, *args, **kwargs):
        self.user_collections = kwargs.pop("user_collections")
        super().__init__(*args, **kwargs)
        self.fields["collection"].choices = ((x.id, x.name) for x in self.user_collections)

    def clean_collection(self):
        collection = self.cleaned_data.get("collection")
        if not collection:
            raise forms.ValidationError("You must select a collection before continuing.")
        return collection


class CollectionDatasetForm(forms.ModelForm):
    deleted = forms.BooleanField(label="DELETE?", required=False)

    class Meta:
        model = CollectionDatasetMembership
        fields = ["dataset", "deleted"]


class CollectionVisualisationForm(forms.ModelForm):
    deleted = forms.BooleanField(label="DELETE?", required=False)

    class Meta:
        model = CollectionVisualisationCatalogueItemMembership
        fields = ["visualisation", "deleted"]


class CollectionUserForm(forms.ModelForm):
    deleted = forms.BooleanField(label="DELETE?", required=False)

    class Meta:
        model = CollectionUserMembership
        fields = ["user", "deleted"]


class CollectionUserAddForm(GOVUKDesignSystemForm):
    email = GOVUKDesignSystemEmailField(
        label="Enter the email address for users you’d like to have access to this collection",
        required=True,
        error_messages={"required": "You must enter a valid email address"},
        widget=GOVUKDesignSystemTextWidget(
            label_size="m",
            extra_label_classes="govuk-!-margin-bottom-6 govuk-!-font-weight-regular",
        ),
    )
