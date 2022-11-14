from django import forms

from dataworkspace.apps.data_collections.models import (
    CollectionDatasetMembership,
    CollectionVisualisationCatalogueItemMembership,
)
from dataworkspace.forms import (
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadiosWidget,
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
