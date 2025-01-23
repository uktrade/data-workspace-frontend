
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
    content = settings.banner_content if settings else ""
    published = settings.banner_live if settings else ""
    end_date = settings.banner_link_text if settings else ""

    return {"content": content,
            "published": published,
            "end_date": end_date}
