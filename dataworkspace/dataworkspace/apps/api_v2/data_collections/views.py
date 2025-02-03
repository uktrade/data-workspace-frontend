from rest_framework import serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v2.datasets.serializers import (
    DatasetSerializer,
    VisualisationDatasetSerializer,
)
from dataworkspace.apps.api_v2.pagination import LastModifiedCursorPagination
from dataworkspace.apps.data_collections.models import Collection


class DataCollectionSerializer(serializers.ModelSerializer):
    collection_url = serializers.SerializerMethodField()
    datasets = DatasetSerializer(many=True)
    visualisation_catalogue_items = VisualisationDatasetSerializer(many=True)

    def get_collection_url(self, obj):
        return obj.get_absolute_url()

    class Meta:
        model = Collection
        fields = ["name", "datasets", "visualisation_catalogue_items", "collection_url"]


class DataCollectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Collection.objects.all()
    serializer_class = DataCollectionSerializer
    pagination_class = LastModifiedCursorPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user, deleted=False)
