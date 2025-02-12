from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q

from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.api_v1.data_insights.serializers import OwnerInsightsSerializer
from dataworkspace.apps.datasets.models import DataSetType


class OwnerInsightsViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = (
        get_user_model()
        .objects.annotate(
            dataset_count=Count(
                "dataset",
                filter=~Q(dataset__type=DataSetType.DATACUT)
                & Q(dataset__published=True)
                & (
                    Q(dataset__information_asset_manager=OuterRef("id"))
                    | Q(dataset__information_asset_owner=OuterRef("id"))
                ),
            )
        )
        .filter(dataset_count__gt=0)
    )
    serializer_class = OwnerInsightsSerializer
    pagination_class = PageNumberPagination
