from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v1.eventlog.serializers import EventLogSerializer
from dataworkspace.apps.api_v1.mixins import TimestampFilterMixin
from dataworkspace.apps.eventlog.models import EventLog


class TimestampPageNumberPagination(PageNumberPagination):
    ordering = ("-timestamp", "id")
    page_size_query_param = "page_size"
    max_page_size = 10_000


class RecentItemsViewSet(TimestampFilterMixin, viewsets.ModelViewSet):
    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer
    pagination_class = TimestampPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(event_type=EventLog.TYPE_DATASET_VIEW)
