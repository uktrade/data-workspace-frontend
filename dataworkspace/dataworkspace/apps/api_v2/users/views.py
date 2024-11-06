from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dataworkspace.apps.api_v2.users.serializers import (
    PendingAuthorizedUsersSerializer,
)
from dataworkspace.apps.api_v2.pagination import CreatedDateCursorPagination
from dataworkspace.apps.datasets.models import (
    PendingAuthorizedUsers,
)


class PendingAuthorizedUsersViewSet(viewsets.ReadOnlyModelViewSet):
    summary_serializer_class = PendingAuthorizedUsersSerializer
    queryset = PendingAuthorizedUsers.objects.all()
    pagination_class = CreatedDateCursorPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def summary(self, request, pk):
        dataset = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.summary_serializer_class(dataset)
        return Response(serializer.data)
