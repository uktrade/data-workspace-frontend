import re

from django import forms
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionUserMembership,
    CollectionVisualisationCatalogueItemMembership,
)
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemEmailField,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemRichTextField,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaWidget,
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
        self.fields["collection"].choices.append(
            ("add_to_new_collection", "Add to new collection")
        )

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
        error_messages={
            "required": "You must enter a valid email address",
            "invalid": "You must enter a valid email address",
        },
        widget=GOVUKDesignSystemTextWidget(
            label_size="m",
            extra_label_classes="govuk-!-margin-bottom-6 govuk-!-font-weight-regular",
        ),
    )

    def __init__(self, *args, **kwargs):
        self.collection = kwargs.pop("collection")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        user = get_user_model().objects.filter(email=self.cleaned_data["email"]).first()
        if user is None:
            raise forms.ValidationError(
                "The user you are sharing with must have a DIT staff SSO account"
            )
        if self.collection.owner == user:
            raise forms.ValidationError(f"{user.email} already has access to this collection")
        if self.collection.user_memberships.live().filter(user=user).exists():
            raise forms.ValidationError(f"{user.email} already has access to this collection")
        return self.cleaned_data["email"]


class CollectionNotesForm(GOVUKDesignSystemModelForm):
    notes = GOVUKDesignSystemRichTextField(required=False)

    class Meta:
        model = Collection
        fields = ["notes"]


class CollectionEditForm(GOVUKDesignSystemModelForm):
    name = GOVUKDesignSystemCharField(
        label="Collection name",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False),
        error_messages={"required": "You must enter the collection name"},
    )
    description = GOVUKDesignSystemCharField(
        label="Description (optional)",
        required=False,
        widget=GOVUKDesignSystemTextareaWidget(label_is_heading=False),
    )

    class Meta:
        model = Collection
        fields = ["name", "description"]

    def clean_description(self):
        # Do not allow newlines in the description
        return re.sub(r"[\r\n]+", " ", self.cleaned_data["description"])
