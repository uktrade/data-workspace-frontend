from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from dataworkspace.apps.api_v1.eventlog.serializers import EventLogSerializer
from dataworkspace.apps.eventlog.models import EventLog


class EventLogCursorPagination(CursorPagination):
    ordering = ('timestamp',)


class EventLogViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer
    pagination_class = EventLogCursorPagination
