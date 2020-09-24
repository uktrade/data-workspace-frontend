from datetime import datetime, timedelta

from celery.utils.log import get_task_logger
from django.core.cache import cache

from dataworkspace.apps.explorer.models import QueryLog
from dataworkspace.cel import celery_app


logger = get_task_logger(__name__)


@celery_app.task()
def truncate_querylogs(days):
    qs = QueryLog.objects.filter(run_at__lt=datetime.now() - timedelta(days=days))
    logger.info('Deleting %s QueryLog objects older than %s days.', qs.count, days)
    qs.delete()
    logger.info('Done deleting QueryLog objects.')


@celery_app.task()
def build_schema_cache_async(connection_alias, schema=None, table=None):
    from .schema import (  # pylint: disable=import-outside-toplevel, cyclic-import
        build_schema_info,
        connection_schema_cache_key,
    )

    ret = build_schema_info(connection_alias, schema, table)
    cache.set(connection_schema_cache_key(connection_alias), ret)
    return ret
