# pylint: disable-all

from .base import *  # noqa

DEBUG = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "ecs": {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
        "verbose": {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
    },
    "handlers": {"dev": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "loggers": {
        "app": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "test": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "dataworkspace": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "celery": {"handlers": ["dev"], "level": "INFO", "propagate": False},
    },
}
