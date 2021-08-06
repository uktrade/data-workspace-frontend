# pylint: disable-all

from .base import *  # noqa

DEBUG = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'ecs': {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
        "verbose": {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
    },
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}},
    'loggers': {
        'django.db.backend': {'handlers': ['console'], 'level': 'DEBUG'},
        'app': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
        'test': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
        'dataworkspace': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

AWS_S3_ENDPOINT_URL = env.get('AWS_S3_ENDPOINT_URL', None)  # noqa F405
