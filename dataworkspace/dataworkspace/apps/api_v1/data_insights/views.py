from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q

from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.api_v1.data_insights.serializers import OwnerInsightsSerializer
from dataworkspace.apps.datasets.models import DataSet, DataSetType


class OwnerInsightsViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = (
        get_user_model()
        .objects.annotate(
            has_datasets=Exists(
                DataSet.objects.exclude(type=DataSetType.DATACUT).filter(
                    Q(information_asset_manager=OuterRef("id"))
                    | Q(information_asset_owner=OuterRef("id"))
                )
            )
        )
        .filter(has_datasets=True)
    )
    serializer_class = OwnerInsightsSerializer
    pagination_class = PageNumberPagination
