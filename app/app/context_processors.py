from django.conf import (
    settings,
)


def root_href(request):
    return {'root_href': f'{request.scheme}://{settings.APPLICATION_ROOT_DOMAIN}/'}
