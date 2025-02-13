from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from dataworkspace.apps.api_v1.data_insights.serializers import OwnerInsightsSerializer
from dataworkspace.apps.datasets.models import DataSet, DataSetType


class OwnerInsightsViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = DataSet.objects.live()
    serializer_class = OwnerInsightsSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self, *args, **kwargs):
        # the lead id
        user_id = self.request.query_params.get("user_id")
        return (
            super()
            .get_queryset()
            .filter(
                Q(published=True)
                & (Q(information_asset_manager=user_id) | Q(information_asset_owner=user_id))
            )
            .exclude(type=DataSetType.DATACUT)
        )

    @action(detail=False, methods=["get"])
    def get_owner_insights(self, request, *args, **kwargs):
        serializer = self.serializer_class(self.get_queryset())
        user_id = self.request.query_params.get("user_id")
        user = get_user_model().objects.get(pk=user_id)
        data = [serializer.data | {"user_id": user.id, "email": user.email}]
        return Response({"results": data, "next": None, "previous": None}, status=status.HTTP_200_OK)
