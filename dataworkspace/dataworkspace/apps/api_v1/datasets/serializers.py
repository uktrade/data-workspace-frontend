from django.utils.html import strip_tags
from rest_framework import serializers

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    SourceTable,
    ToolQueryAuditLog,
    ToolQueryAuditLogTable,
)

_PURPOSES = {
    DataSetType.DATACUT: "Data cut",
    DataSetType.MASTER: "Master dataset",
    DataSetType.REFERENCE: "Reference data",
    DataSetType.VISUALISATION: "Visualisation",
}


class SourceTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceTable
        fields = (
            "id",
            "name",
            "schema",
            "table",
        )


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
    source_tables = serializers.SerializerMethodField()
    slug = serializers.CharField()
    licence_url = serializers.CharField()
    restrictions_on_usage = serializers.CharField()
    user_access_type = serializers.CharField()
    authorized_email_domains = serializers.ListField()
    is_draft = serializers.BooleanField(source="draft")
    dictionary_published = serializers.BooleanField(source="dictionary")
    user_ids = serializers.ListField()

    def to_representation(self, instance):
        instance = super().to_representation(instance)
        instance["description"] = (
            strip_tags(instance["description"]).replace("\r\n", "")
            if instance["description"]
            else None
        )
        instance["purpose"] = _PURPOSES[int(instance["purpose"])]
        instance["source_tags"] = instance["source_tags"] or None
        instance["licence"] = instance["licence"] or None
        instance["personal_data"] = instance["personal_data"] or None
        instance["retention_policy"] = instance["retention_policy"] or None
        instance["user_access_type"] = instance["user_access_type"]
        instance["authorized_email_domains"] = instance["authorized_email_domains"]
        return instance

    def get_source_tables(self, instance):
        if instance["purpose"] == DataSetType.MASTER:
            return SourceTableSerializer(
                SourceTable.objects.filter(dataset_id=instance["id"]), many=True
            ).data
        return []


class ToolQueryAuditLogTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolQueryAuditLogTable
        fields = ["id", "schema", "table"]


class ToolQueryAuditLogSerializer(serializers.ModelSerializer):
    database = serializers.StringRelatedField()
    tables = ToolQueryAuditLogTableSerializer(many=True, read_only=True)
    query_sql = serializers.CharField(source="truncated_query_sql")

    class Meta:
        model = ToolQueryAuditLog
        fields = [
            "id",
            "user",
            "database",
            "query_sql",
            "rolename",
            "timestamp",
            "tables",
        ]
