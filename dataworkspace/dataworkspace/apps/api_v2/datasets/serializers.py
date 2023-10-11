from django.db.models import Q
from rest_framework import serializers

from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
)
from dataworkspace.apps.eventlog.models import EventLog


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSet
        fields = ("id", "name")


class DatasetStatsSerializer(serializers.ModelSerializer):
    page_views = serializers.SerializerMethodField()
    table_queries = serializers.SerializerMethodField()
    table_views = serializers.SerializerMethodField()
    collection_count = serializers.SerializerMethodField()
    bookmark_count = serializers.SerializerMethodField()

    class Meta:
        model = DataSet
        fields = (
            "page_views",
            "table_queries",
            "table_views",
            "collection_count",
            "bookmark_count",
        )

    def get_page_views(self, obj):
        return obj.events.filter(event_type=EventLog.TYPE_DATASET_VIEW).count()

    def get_table_queries(self, obj):
        return obj.average_unique_users_daily

    def get_table_views(self, obj):
        return obj.events.filter(event_type=EventLog.TYPE_DATA_TABLE_VIEW).count()

    def get_collection_count(self, obj):
        return obj.collection_set.count()

    def get_bookmark_count(self, obj):
        return obj.bookmark_count()


class ReferenceDatasetSerializer(DatasetSerializer):
    class Meta:
        model = ReferenceDataset
        fields = ("id", "name")


class ReferenceDatasetStatsSerializer(DatasetStatsSerializer):
    class Meta:
        model = ReferenceDataset
        fields = (
            "page_views",
            "table_queries",
            "table_views",
            "collection_count",
            "bookmark_count",
        )

    def get_collection_count(self, obj):
        return obj.reference_dataset_inheriting_from_dataset.collection_set.count()


class VisualisationDatasetSerializer(DatasetSerializer):
    class Meta:
        model = VisualisationCatalogueItem
        fields = ("id", "name")


class VisualisationDatasetStatsSerializer(DatasetStatsSerializer):
    dashboard_views = serializers.SerializerMethodField()

    class Meta:
        model = VisualisationCatalogueItem
        fields = (
            "page_views",
            "collection_count",
            "dashboard_views",
            "bookmark_count",
        )

    def get_dashboard_views(self, obj):
        return obj.events.filter(
            Q(event_type=EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION)
            | Q(event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION)
            | Q(event_type=EventLog.TYPE_VIEW_VISUALISATION_TEMPLATE)
        ).count()
