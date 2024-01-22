from rest_framework import viewsets

from dataworkspace.apps.maintenance.models import MaintenanceSettings
from dataworkspace.apps.maintenance.serializers import MaintenanceSettingsSerializer


class MaintenanceSettingsViewSet(viewsets.ModelViewSet):
    """
    API Endpoint to return maintenance settings
    """

    queryset = MaintenanceSettings.objects.all()
    serializer_class = MaintenanceSettingsSerializer
