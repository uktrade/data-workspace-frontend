from django.db.models import Q, TextField
from django.db.models.functions import Cast
from django.urls import reverse
from rest_framework import serializers

from dataworkspace.apps.datasets.constants import DataSetType
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
        return f"{obj.average_unique_users_daily:.3f}"

    def get_table_views(self, obj):
        if obj.type == DataSetType.MASTER:
            source_table_ids = obj.sourcetable_set.annotate(
                str_id=Cast("id", output_field=TextField())
            ).values_list("str_id", flat=True)
            return EventLog.objects.filter(
                object_id__in=source_table_ids, event_type=EventLog.TYPE_DATA_TABLE_VIEW
            ).count()

        elif obj.type == DataSetType.DATACUT:
            custom_dataset_table_ids = obj.customdatasetquery_set.annotate(
                str_id=Cast("id", output_field=TextField())
            ).values_list("str_id", flat=True)
            return EventLog.objects.filter(
                object_id__in=custom_dataset_table_ids,
                event_type=EventLog.TYPE_DATA_TABLE_VIEW,
            ).count()

        else:
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


class BookmarkedDatasetSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    name = serializers.CharField()
    url = serializers.SerializerMethodField()
    created = serializers.DateTimeField()

    def get_id(self, obj):
        return obj["dataset_id"]

    def get_url(self, obj):
        return f"{reverse('datasets:dataset_detail', args=(obj['dataset_id'],))}#{obj['slug']}"
