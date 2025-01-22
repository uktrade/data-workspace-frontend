from rest_framework import viewsets

from dataworkspace.apps.notification_banner.models import NotificationBanner
from dataworkspace.apps.notification_banner.serializers import NotificationBannerSerializer


class NotificationBannerViewSet(viewsets.ModelViewSet):
    """
    API Endpoint to return banner settings
    """

    queryset = NotificationBanner.objects.all()
    serializer_class = NotificationBannerSerializer
