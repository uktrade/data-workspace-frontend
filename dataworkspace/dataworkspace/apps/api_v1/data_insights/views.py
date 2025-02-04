from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.api_v1.data_insights.serializers import OwnerInsightsSerializer


class OwnerInsightsViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = get_user_model().objects.all()
    serializer_class = OwnerInsightsSerializer
    pagination_class = PageNumberPagination
