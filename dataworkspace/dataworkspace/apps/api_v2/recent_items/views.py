from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v1.eventlog.serializers import EventLogSerializer
from dataworkspace.apps.api_v1.mixins import TimestampFilterMixin
from dataworkspace.apps.eventlog.models import EventLog


class TimestampPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class RecentItemsViewSet(TimestampFilterMixin, viewsets.ModelViewSet):
    queryset = EventLog.objects.filter(event_type=EventLog.TYPE_DATASET_VIEW)
    serializer_class = EventLogSerializer
    pagination_class = TimestampPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        all_events = super().get_queryset().filter(user=self.request.user)
        distinct_event_ids = (
            all_events.order_by("object_id", "-timestamp")
            .distinct("object_id")
            .values_list("id", flat=True)
        )
        return all_events.filter(pk__in=distinct_event_ids)
