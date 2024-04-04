from django import forms 
from django.contrib import admin
from dataworkspace.apps.arangodb.models import SourceGraphCollection, SourceGraphCollectionFieldDefinition
from dataworkspace.apps.datasets.models import MasterDataset


class SourceGraphCollectionForm(forms.ModelForm):

    model = SourceGraphCollection

    class Meta:
        fields = (
            "dataset",
            "name",
            "collection",
            "dataset_finder_opted_in",
            "data_grid_enabled",
            "published",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MasterDataset.objects.live()

    def clean(self):
        cleaned = self.cleaned_data
        grid_enabled = cleaned.get("data_grid_enabled", False)

        if grid_enabled:
            raise forms.ValidationError(
                {"data_grid_enabled": "Grid cannot be enabled for graph-type data"}
            )
        
        return cleaned


class SourceGraphCollectionFieldDefinitionInline(admin.TabularInline):
    model = SourceGraphCollectionFieldDefinition
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"
