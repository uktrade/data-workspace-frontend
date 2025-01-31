from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v2.data_insights.serializers import OwnerInsightsSerializer


class OwnerInsightsViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = get_user_model().objects.all()
    serializer_class = OwnerInsightsSerializer
    pagination_class = PageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
