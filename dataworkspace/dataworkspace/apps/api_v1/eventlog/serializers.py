from rest_framework import serializers

from dataworkspace.apps.datasets.models import DataSet, ReferenceDataset
from dataworkspace.apps.eventlog.models import EventLog


class EventLogDatasetSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = DataSet
        fields = ('id', 'type', 'name')

    def get_type(self, obj):
        return obj.get_type_display()


class EventLogReferenceDatasetSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceDataset
        fields = ('id', 'type', 'name')

    def get_type(self, obj):
        return obj.get_type_display()


class EventLogRelatedObjectField(serializers.RelatedField):
    def to_representation(self, value):
        if isinstance(value, DataSet):
            return EventLogDatasetSerializer(value).data
        if isinstance(value, ReferenceDataset):
            return EventLogReferenceDatasetSerializer(value).data


class EventLogSerializer(serializers.ModelSerializer):
    related_object = EventLogRelatedObjectField(read_only=True)
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = EventLog
        fields = ('id', 'timestamp', 'event_type', 'user_id', 'related_object', 'extra')

    def get_event_type(self, obj):
        return obj.get_event_type_display()
