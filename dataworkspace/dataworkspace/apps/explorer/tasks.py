from datetime import datetime, timedelta

from celery.utils.log import get_task_logger
from django.db import connections
from pytz import utc

from dataworkspace.apps.explorer.models import QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.utils import tempory_query_table_name
from dataworkspace.cel import celery_app


logger = get_task_logger(__name__)


@celery_app.task()
def truncate_querylogs(days):
    qs = QueryLog.objects.filter(run_at__lt=datetime.now() - timedelta(days=days))
    logger.info('Deleting %s QueryLog objects older than %s days.', qs.count, days)
    qs.delete()
    logger.info('Done deleting QueryLog objects.')


@celery_app.task()
def cleanup_playground_sql_table():
    older_than = timedelta(days=14)
    oldest_date_to_retain = datetime.now(tz=utc) - older_than

    logger.info(
        "Cleaning up Data Explorer PlaygroundSQL rows older than %s",
        oldest_date_to_retain,
    )

    count = 0
    for play_sql in PlaygroundSQL.objects.filter(created_at__lte=oldest_date_to_retain):
        play_sql.delete()
        count += 1

    logger.info("Delete %s PlaygroundSQL rows", count)


@celery_app.task()
def cleanup_temporary_query_tables():
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    logger.info(
        "Cleaning up Data Explorer temporary query tables older than %s", one_day_ago
    )

    for query_log in QueryLog.objects.filter(run_at__lte=one_day_ago):
        with connections[query_log.connection].cursor() as cursor:
            table_name = tempory_query_table_name(query_log.run_by_user, query_log.id)
            logger.info("Dropping temprary query table %s", table_name)
            cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
