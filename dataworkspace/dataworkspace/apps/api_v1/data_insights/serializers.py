from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from rest_framework import serializers

from dataworkspace.apps.core.utils import table_exists
from dataworkspace.apps.datasets.data_dictionary.service import DataDictionaryService
from dataworkspace.apps.datasets.models import DataSet, SourceTable
from dataworkspace.apps.request_access.models import AccessRequest


class OwnerInsightsSerializer(serializers.ModelSerializer):
    # dataset_description_change = serializers.SerializerMethodField()
    owned_datasets = serializers.SerializerMethodField()
    owned_source_tables = serializers.SerializerMethodField()

    class Meta:
        model = DataSet
        fields = (
            "owned_datasets",
            "owned_source_tables",
            # "dataset_description_change",
        )

    """ Leave until we can collect enough data to require this
    def get_dataset_description_change(self, user):
        dataset_ids = (
            self.user_datasets(user)
            .annotate(str_id=Cast("id", output_field=TextField()))
            .values_list("str_id", flat=True)
        )
        return EventLog.objects.filter(
            object_id__in=dataset_ids,
            event_type=EventLog.TYPE_CHANGED_DATASET_DESCRIPTION,
        ).values("object_id", "timestamp")
    """

    def get_owned_datasets(self, datasets):
        return datasets.annotate(
            access_request_count=Coalesce(
                Subquery(
                    AccessRequest.objects.filter(
                        Q(catalogue_item_id=OuterRef("id")) & Q(data_access_status="waiting")
                    )
                    .values("catalogue_item_id")
                    .annotate(count=Count("id"))
                    .values("count"),
                    output_field=IntegerField(),
                ),
                0,
            )
        ).values("id", "name", "access_request_count")

    def get_owned_source_tables(self, datasets):
        dataset_ids = datasets.values_list("id", flat=True).distinct()
        source_tables = SourceTable.objects.filter(Q(dataset__id__in=dataset_ids))
        service_ds = DataDictionaryService()
        source_table_response = []
        for source_table in source_tables:
            source_table_response.append(
                {
                    "id": source_table.id,
                    "name": source_table.name,
                    "data_dictionaries": [
                        {
                            "name": item.name,
                            "data_type": item.data_type,
                            "definition": item.definition,
                        }
                        for item in service_ds.get_dictionary(source_table.id).items
                    ],
                    "pipeline_last_run_success": source_table.pipeline_last_run_success(),
                }
            )
        return source_table_response
