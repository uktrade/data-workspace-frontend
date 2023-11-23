from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v2.datasets.serializers import DatasetSerializer
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.eventlog.models import EventLog


class YourBookmarkPageNumberPagination(PageNumberPagination):
    ordering = ("-timestamp", "name")
    page_size_query_param = "page_size"
    max_page_size = 10_000


class YourBookmarksViewSet(viewsets.ModelViewSet):
    queryset = DataSet.objects.all()
    serializer_class = DatasetSerializer
    pagination_class = YourBookmarkPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                user_has_bookmarked=self.request.user, event_type=EventLog.TYPE_DATASET_BOOKMARKED
            )
        )
