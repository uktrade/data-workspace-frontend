from django import forms
from django.contrib import admin
from dataworkspace.apps.arangodb.models import (
    SourceGraphCollectionFieldDefinition,
)
from dataworkspace.apps.datasets.models import MasterDataset, SourceGraphCollection


class SourceGraphCollectionForm(forms.ModelForm):
    model = SourceGraphCollection

    class Meta:
        fields = (
            "dataset",
            "name",
            "collection",
            "dataset_finder_opted_in",
            "published",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MasterDataset.objects.live()


class SourceGraphCollectionFieldDefinitionInline(admin.TabularInline):
    model = SourceGraphCollectionFieldDefinition
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"
