# Monkey-patching should happen as early as possible ...
# pylint: disable=multiple-statements,wrong-import-position,wrong-import-order

# fmt: off
from psycogreen.gevent import patch_psycopg; patch_psycopg()  # noqa: E402,E702
# fmt: on

import logging

from celery import Celery
from celery.signals import after_setup_logger
from django.conf import settings

celery_app = Celery("dataworkspace")

celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks()

# this *shouldn't* need to be applied directly but
# automatically configured via ^^ config_from_object
celery_app.conf.task_routes = settings.CELERY_ROUTES


@after_setup_logger.connect
def setup_loggers(*args, **kwargs):
    logging.config.dictConfig(settings.LOGGING)
