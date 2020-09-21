from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.db import connections as djcs


class ExplorerAppConfig(AppConfig):

    name = 'explorer'

    def ready(self):
        from dataworkspace.apps.explorer.schema import (  # pylint: disable=import-outside-toplevel
            build_async_schemas,
        )

        _validate_connections()
        build_async_schemas()


def _get_default():
    from dataworkspace.apps.explorer.app_settings import (  # pylint: disable=import-outside-toplevel
        EXPLORER_DEFAULT_CONNECTION,
    )

    return EXPLORER_DEFAULT_CONNECTION


def _get_explorer_connections():
    from dataworkspace.apps.explorer.app_settings import (  # pylint: disable=import-outside-toplevel
        EXPLORER_CONNECTIONS,
    )

    return EXPLORER_CONNECTIONS


def _validate_connections():

    # Validate connections
    if _get_default() not in _get_explorer_connections().values():
        raise ImproperlyConfigured(
            'EXPLORER_DEFAULT_CONNECTION is %s, but that alias is not'
            ' present in the values of EXPLORER_CONNECTIONS' % _get_default()
        )

    for name, conn_name in _get_explorer_connections().items():
        if conn_name not in djcs:
            raise ImproperlyConfigured(
                'EXPLORER_CONNECTIONS contains (%s, %s), but %s'
                ' is not a valid Django DB connection.' % (name, conn_name, conn_name)
            )
