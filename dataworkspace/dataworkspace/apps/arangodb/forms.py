from django import forms
from django.contrib import admin
from dataworkspace.apps.arangodb.models import (
    ArangoDocumentCollectionFieldDefinition,
)
from dataworkspace.apps.datasets.models import MasterDataset, ArangoDocumentCollection


class ArangoDocumentCollectionForm(forms.ModelForm):
    model = ArangoDocumentCollection

    class Meta:
        fields = (
            "dataset",
            "name",
            "collection",
            "dataset_finder_opted_in",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MasterDataset.objects.live()


class ArangoDocumentCollectionFieldDefinitionInline(admin.TabularInline):
    model = ArangoDocumentCollectionFieldDefinition
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"
