from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated


from .serializers import RecentToolsSerializer
from dataworkspace.apps.api_v1.mixins import TimestampFilterMixin
from dataworkspace.apps.eventlog.models import EventLog


class TimestampPageNumberPagination(PageNumberPagination):
    ordering = ("-timestamp", "id")
    page_size_query_param = "page_size"
    max_page_size = 100


class RecentToolsViewSet(TimestampFilterMixin, viewsets.ModelViewSet):
    queryset = EventLog.objects.filter(
        event_type__in=[EventLog.TYPE_USER_TOOL_LINK_STARTED, EventLog.TYPE_USER_TOOL_ECS_STARTED]
    )
    serializer_class = RecentToolsSerializer
    pagination_class = TimestampPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
