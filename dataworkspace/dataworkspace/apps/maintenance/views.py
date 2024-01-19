from rest_framework import viewsets

from dataworkspace.apps.maintenance.admin import MaintenanceSettingsAdmin
from dataworkspace.apps.maintenance.serializers import MaintenanceSettingsSerializer


class MaintenanceSettingsViewSet(viewsets.ModelViewSet):
    """
    API Endpoint to return maintenance settings
    """
    queryset = MaintenanceSettingsAdmin.objects.all()
    serializer_class = MaintenanceSettingsSerializer
