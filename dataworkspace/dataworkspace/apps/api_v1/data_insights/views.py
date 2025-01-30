from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from dataworkspace.apps.api_v1.data_insights.serializers import DataInsightsSerializer
from dataworkspace.apps.datasets.models import (
    DataSet,
)


class DataInsightsViewSet(viewsets.ModelViewSet):
    queryset = DataSet.objects.all()
    serializer_class = DataInsightsSerializer
    pagination_class = PageNumberPagination
