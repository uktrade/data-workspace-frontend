from maintenance_mode.core import set_maintenance_mode

from dataworkspace.apps.banner.models import bannerSettings


def get_banner_settings():
    """Fetch the bannerSettings object from the database."""
    return bannerSettings.objects.first()


def banner_context(request):
    """
    Return a dictionary with the banner text from the bannerSettings object.
    If no bannerSettings object exists, return an empty string.
    """
    settings = get_banner_settings()
    banner_text = settings.banner_text if settings else ""
    banner_time = settings.banner_time if settings else ""

    return {"banner_text": banner_text, "banner_time": banner_time}


def update_banner_status():
    """
    Update banner mode state with the current banner settings.
    """
    settings = get_banner_settings()
    banner_toggle = settings.banner_toggle if settings else False
    set_maintenance_mode(banner_toggle)


class BannerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Middleware that updates the banner status for every request.
        """
        update_banner_status()
        response = self.get_response(request)
        return response
