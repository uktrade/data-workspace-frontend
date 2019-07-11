from django.conf import (
    settings,
)


def common(request):
    return {
        'root_href': f'{request.scheme}://{settings.APPLICATION_ROOT_DOMAIN}/',
        'support_url': settings.SUPPORT_URL,
        'google_analytics_site_id': settings.GOOGLE_ANALYTICS_SITE_ID
    }
