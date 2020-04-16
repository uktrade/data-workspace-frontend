from django.forms import Textarea

from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
from dataworkspace.forms import GOVUKDesignSystemModelForm


class VisualisationsUICatalogueItemForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = VisualisationCatalogueItem
        fields = [
            'short_description',
            'description',
            'enquiries_contact',
            'secondary_enquiries_contact',
            'information_asset_manager',
            'information_asset_owner',
            'licence',
            'retention_policy',
            'personal_data',
            'restrictions_on_usage',
        ]
        widgets = {"retention_policy": Textarea, "restrictions_on_usage": Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['short_description'].error_messages[
            'required'
        ] = "The visualisation must have a summary"
