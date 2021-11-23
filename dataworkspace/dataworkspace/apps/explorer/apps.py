from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections as djcs


class ExplorerAppConfig(AppConfig):

    name = "dataworkspace.apps.explorer"

    def ready(self):
        _validate_connections()


def _get_default():
    return settings.EXPLORER_DEFAULT_CONNECTION


def _get_explorer_connections():
    return settings.EXPLORER_CONNECTIONS


def _validate_connections():
    if _get_default() not in _get_explorer_connections().values():
        raise ImproperlyConfigured(
            "EXPLORER_DEFAULT_CONNECTION is %s, but that alias is not"
            " present in the values of EXPLORER_CONNECTIONS" % _get_default()
        )

    for name, conn_name in _get_explorer_connections().items():
        if conn_name not in djcs:
            raise ImproperlyConfigured(
                "EXPLORER_CONNECTIONS contains (%s, %s), but %s"
                " is not a valid Django DB connection." % (name, conn_name, conn_name)
            )
