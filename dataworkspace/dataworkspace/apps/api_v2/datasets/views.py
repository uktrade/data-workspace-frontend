from django.db.models import Q
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dataworkspace.apps.api_v2.datasets.serializers import (
    DatasetSerializer,
    DatasetStatsSerializer,
    ReferenceDatasetSerializer,
    ReferenceDatasetStatsSerializer,
    VisualisationDatasetSerializer,
    VisualisationDatasetStatsSerializer,
)
from dataworkspace.apps.api_v2.pagination import CreatedDateCursorPagination
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
)
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
)


class DatasetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DatasetSerializer
    stats_serializer_class = DatasetStatsSerializer
    queryset = DataSet.objects.live()
    pagination_class = CreatedDateCursorPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        qs_filter = Q(published=True)
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.MASTER)
        ):
            qs_filter |= Q(published=False, type=DataSetType.MASTER)

        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.DATACUT)
        ):
            qs_filter |= Q(published=False, type=DataSetType.DATACUT)

        return qs.filter(qs_filter)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk):
        dataset = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.stats_serializer_class(dataset)
        return Response(serializer.data)


class ReferenceDatasetViewSet(DatasetViewSet):
    queryset = ReferenceDataset.objects.live()
    serializer_class = ReferenceDatasetSerializer
    stats_serializer_class = ReferenceDatasetStatsSerializer

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        qs_filter = Q(published=True)
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.REFERENCE)
        ):
            qs_filter |= Q(published=False)
        return qs.filter(qs_filter)


class VisualisationViewSet(DatasetViewSet):
    queryset = VisualisationCatalogueItem.objects.live()
    serializer_class = VisualisationDatasetSerializer
    stats_serializer_class = VisualisationDatasetStatsSerializer

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        qs_filter = Q(published=True)
        if user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.VISUALISATION)
        ):
            qs_filter |= Q(published=False)
        return qs.filter(qs_filter)
