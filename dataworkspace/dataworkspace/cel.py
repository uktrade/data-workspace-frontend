import logging

from celery import Celery
from celery.signals import after_setup_logger

from django.conf import settings

celery_app = Celery("dataworkspace")

celery_app.config_from_object("django.conf:settings", namespace="CELERY")

celery_app.task_routes = {
    "dataworkspace.apps.applications.spawner.spawn": {"queue": "spawner_spawn"},
    "dataworkspace.apps.explorer.tasks.*": {"queue": "data_explorer"},
}

celery_app.autodiscover_tasks()


@after_setup_logger.connect
def setup_loggers(*args, **kwargs):
    logging.config.dictConfig(settings.LOGGING)
