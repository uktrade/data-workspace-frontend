from django.db.models import F
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v1.mixins import TimestampFilterMixin
from dataworkspace.apps.eventlog.models import EventLog

from .serializers import RecentToolsSerializer


class TimestampPageNumberPagination(PageNumberPagination):
    ordering = ("-timestamp", "id")
    page_size_query_param = "page_size"
    max_page_size = 100


class RecentToolsViewSet(TimestampFilterMixin, viewsets.ModelViewSet):
    queryset = EventLog.objects.all()
    serializer_class = RecentToolsSerializer
    pagination_class = TimestampPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        all_events = EventLog.objects.filter(
            user=self.request.user,
            event_type__in=[
                EventLog.TYPE_USER_TOOL_LINK_STARTED,
                EventLog.TYPE_USER_TOOL_ECS_STARTED,
            ],
        ).annotate(tool_name=F("extra__tool"))
        distinct_events = all_events.order_by("tool_name", "-timestamp").distinct("tool_name")
        return all_events.filter(id__in=[event.id for event in distinct_events]).order_by(
            "-timestamp"
        )
