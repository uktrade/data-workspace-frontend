from __future__ import absolute_import, unicode_literals

import os
from datetime import timedelta

from celery import Celery
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'explorer.settings.base')

app = Celery('explorer')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_schedule = {}

for alias in settings.EXPLORER_CONNECTIONS:
    app.conf.beat_schedule.update(
        {
            f"trigger-build-schema-{alias}": {
                "task": "explorer.tasks.build_schema_cache_async",
                "schedule": timedelta(minutes=8),
                "args": (alias,),
            }
        }
    )
