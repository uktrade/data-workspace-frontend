from rest_framework import status, mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import NotificationBannerSerializer
from dataworkspace.apps.notification_banner.models import NotificationBanner


class UpdateNotificationBanner(mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    queryset = NotificationBanner.objects.all()
    serializer_class = NotificationBannerSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        payload = {
            "last_chance_days": serializer.validated_data.get("last_chance_days"),
            "end_date": serializer.validated_data.get("end_date"),
        }
        serializer.save(**payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
