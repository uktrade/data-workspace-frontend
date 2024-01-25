from django.contrib import admin

from dataworkspace.apps.maintenance.models import MaintenanceSettings


@admin.register(MaintenanceSettings)
class MaintenanceSettingsAdmin(admin.ModelAdmin):
    list_display = ("maintenance_toggle", "maintenance_text", "contact_email")
