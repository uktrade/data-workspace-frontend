from rest_framework import viewsets

from dataworkspace.apps.banner.models import BannerSettings
from dataworkspace.apps.banner.serializers import BannerSettingsSerializer


class BannerSettingsViewSet(viewsets.ModelViewSet):
    """
    API Endpoint to return banner settings
    """

    queryset = BannerSettings.objects.all()
    serializer_class = BannerSettingsSerializer
