from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from dataworkspace.apps.api_v1.applications.serializers import (
    ApplicationInstanceReportSerializer,
)
from dataworkspace.apps.applications.models import ApplicationInstanceReport


class ApplicationInstanceReportCursorPagination(CursorPagination):
    ordering = ('id',)


class ApplicationInstanceReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list application instance report items for consumption by data flow.
    """

    queryset = ApplicationInstanceReport.objects.all()
    serializer_class = ApplicationInstanceReportSerializer
    pagination_class = ApplicationInstanceReportCursorPagination
