from rest_framework import serializers

from dataworkspace.apps.maintenance.models import MaintenanceSettings


class MaintenanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceSettings
        fields = "__all__"
