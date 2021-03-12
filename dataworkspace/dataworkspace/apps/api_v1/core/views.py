from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.core.models import UserSatisfactionSurvey
from dataworkspace.apps.api_v1.core.serializers import UserSatisfactionSurveySerializer


class UserSatisfactionSurveyViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list user satisfaction survey results for ingestion by data flow
    """

    queryset = UserSatisfactionSurvey.objects.all()
    serializer_class = UserSatisfactionSurveySerializer
    pagination_class = PageNumberPagination
