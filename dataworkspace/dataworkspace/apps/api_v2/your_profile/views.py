from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework import status, mixins
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.accounts.models import (
    Profile
)

from .serializers import ProfileSerializer


class ProfileViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def list(self, request):
        qs = self.queryset.filter(user=self.request.user)
        serializer = self.serializer_class(qs, many=True)
        return Response(serializer.data)

    def perform_update(self, serializer):
        show_bookmarks = serializer.validated_data.get("show_bookmarks")
        serializer.save(show_bookmarks=show_bookmarks)
        return Response(serializer.data)
