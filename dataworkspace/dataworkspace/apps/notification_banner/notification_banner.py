
from dataworkspace.apps.notification_banner.models import NotificationBanner


def get_notification_banner():
    """Fetch the NotificationBanner object from the database."""
    notification_banner = NotificationBanner.objects.first()
    return notification_banner


def notification_banner_context(request):
    """
    Return a dictionary with the banner text from the NotificationBanner object.
    If no NotificationBanner object exists, return an empty string.
    """
    settings = get_notification_banner()
    banner_text = settings.banner_text if settings else ""
    banner_link_text = settings.banner_link_text if settings else ""
    banner_link = settings.banner_link if settings else ""
    banner_live = settings.banner_live if settings else ""
    banner_end_date = settings.banner_link_text if settings else ""

    return {"banner_text": banner_text,
            "banner_link_text": banner_link_text,
            "banner_link": banner_link,
            "banner_live": banner_live,
            "banner_end_date": banner_end_date}
