from django.db.models import Q
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dataworkspace.apps.api_v1.mixins import TimestampFilterMixin
from dataworkspace.apps.datasets.models import DataSet


class TimestampPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class ManagedDataViewSet(TimestampFilterMixin, viewsets.ModelViewSet):
    queryset = DataSet.objects.live()
    pagination_class = TimestampPageNumberPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.request.user.id
        return (
            super()
            .get_queryset()
            .filter(
                (Q(information_asset_manager=user_id) | Q(information_asset_owner=user_id))
                & Q(published=True)
            )
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request, *args, **kwargs):
        kwargs = "?q=&sort=relevance&my_datasets=owned"
        managed_data_url = f"{reverse('datasets:find_datasets')}{kwargs}"
        count = self.get_queryset().count()
        results = [{"count": count, "managed_data_url": managed_data_url}] if count > 0 else []
        return Response({"results": results})
