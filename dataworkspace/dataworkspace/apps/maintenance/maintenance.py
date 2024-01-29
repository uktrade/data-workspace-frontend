from maintenance_mode.core import set_maintenance_mode

from dataworkspace.apps.maintenance.models import MaintenanceSettings


def get_maintenance_settings():
    """Fetch the MaintenanceSettings object from the database."""
    return MaintenanceSettings.objects.first()


def maintenance_context(request):
    """
    Return a dictionary with the maintenance text from the MaintenanceSettings object.
    If no MaintenanceSettings object exists, return an empty string.
    """
    settings = get_maintenance_settings()
    maintenance_text = settings.maintenance_text if settings else ""
    contact_email = "Test"
    return {"maintenance_text": maintenance_text, "contact_email": contact_email}


def update_maintenance_status():
    """
    Update maintenance mode state with the current maintenance settings.
    """
    settings = get_maintenance_settings()
    maintenance_toggle = settings.maintenance_toggle if settings else False
    set_maintenance_mode(maintenance_toggle)


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Middleware that updates the maintenance status for every request.
        """
        update_maintenance_status()
        response = self.get_response(request)
        return response
