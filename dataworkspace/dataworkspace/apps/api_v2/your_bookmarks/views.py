from django.db.models import F, IntegerField, Value
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v2.datasets.serializers import BookmarkedDatasetSerializer
from dataworkspace.apps.api_v2.your_bookmarks.utils import filter_bookmarks
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
)


class YourBookmarkPageNumberPagination(PageNumberPagination):
    ordering = "-created"
    page_size_query_param = "page_size"
    max_page_size = 10_000


class YourBookmarksViewSet(viewsets.ModelViewSet):
    queryset = DataSet.objects.all()
    serializer_class = BookmarkedDatasetSerializer
    pagination_class = YourBookmarkPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        fields = ["dataset_id", "data_type", "name", "slug", "created"]
        return (
            filter_bookmarks(
                DataSet.objects.live()
                .exclude(type=DataSetType.REFERENCE)
                .annotate(dataset_id=F("id"), data_type=F("type")),
                self.request.user,
            )
            .values(*fields)
            .union(
                filter_bookmarks(
                    ReferenceDataset.objects.live().annotate(
                        dataset_id=F("uuid"),
                        data_type=Value(DataSetType.REFERENCE, IntegerField()),
                    ),
                    self.request.user,
                ).values(*fields)
            )
            .union(
                filter_bookmarks(
                    VisualisationCatalogueItem.objects.live().annotate(
                        dataset_id=F("id"),
                        data_type=Value(DataSetType.VISUALISATION, IntegerField()),
                    ),
                    self.request.user,
                ).values(*fields)
            )
        ).order_by("-created")
