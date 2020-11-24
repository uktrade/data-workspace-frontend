from django.utils.html import strip_tags
from rest_framework import serializers

from dataworkspace.apps.datasets.constants import DataSetType


_PURPOSES = {
    DataSetType.DATACUT.value: 'Data cut',
    DataSetType.MASTER.value: 'Master dataset',
    DataSetType.REFERENCE.value: 'Reference data',
    DataSetType.VISUALISATION.value: 'Visualisation',
}


class CatalogueItemSerializer(serializers.Serializer):
    purpose = serializers.CharField()
    id = serializers.UUIDField()
    name = serializers.CharField()
    short_description = serializers.CharField()
    description = serializers.CharField()
    published = serializers.BooleanField()
    created_date = serializers.DateTimeField()
    published_at = serializers.DateField()
    information_asset_owner = serializers.IntegerField()
    information_asset_manager = serializers.IntegerField()
    enquiries_contact = serializers.IntegerField()
    source_tags = serializers.ListField()
    licence = serializers.CharField()
    personal_data = serializers.CharField()
    retention_policy = serializers.CharField()
    eligibility_criteria = serializers.ListField()

    def to_representation(self, instance):
        instance = super().to_representation(instance)
        instance['description'] = (
            strip_tags(instance['description']).replace('\r\n', '')
            if instance['description']
            else None
        )
        instance['purpose'] = _PURPOSES[int(instance['purpose'])]
        instance['source_tags'] = instance['source_tags'] or None
        instance['licence'] = instance['licence'] or None
        instance['personal_data'] = instance['personal_data'] or None
        instance['retention_policy'] = instance['retention_policy'] or None
        return instance
