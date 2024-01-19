from django.db import models


class MaintenanceSettings(models.Model):
    maintenance_text = models.CharField()
    maintenance_toggle = models.BooleanField()

    def __str__(self):
        return 'Maintenance Settings'

    class Meta:
        verbose_name_plural = "settings"
