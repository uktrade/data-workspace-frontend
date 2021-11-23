from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from dataworkspace.apps.api_v1.applications.serializers import (
    ApplicationInstanceSerializer,
)
from dataworkspace.apps.applications.models import ApplicationInstance


class ApplicationInstanceCursorPagination(CursorPagination):
    ordering = ("id",)


class ApplicationInstanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list application instance items for consumption by data flow.
    """

    queryset = ApplicationInstance.objects.all()
    serializer_class = ApplicationInstanceSerializer
    pagination_class = ApplicationInstanceCursorPagination
