from django.conf import (
    settings,
)


def common(request):
    return {
        'root_href': f'{request.scheme}://{settings.APPLICATION_ROOT_DOMAIN}/',
        'support_url': settings.SUPPORT_URL,
        'inline_edit': settings.DISPLAY_INLINE_EDIT_LINKS,
    }
