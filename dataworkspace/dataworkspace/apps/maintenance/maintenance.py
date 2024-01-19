from dataworkspace.apps.maintenance.models import MaintenanceSettings


def maintenance_context(request):
    settings = MaintenanceSettings.objects.first()
    maintenance_text = settings.maintenance_text if settings else ''
    return {'maintenance_text': maintenance_text}
