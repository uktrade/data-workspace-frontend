from datetime import datetime, timedelta
from time import time

from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.db import connections

from pytz import utc

from dataworkspace.apps.explorer.models import QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.utils import (
    get_user_explorer_connection_settings,
    tempory_query_table_name,
    TYPE_CODES_REVERSED,
    user_explorer_connection,
)
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


def _prefix_column(index, column):
    return f'col_{index}_{column}'


@celery_app.task()
def execute_query(query_sql, query_connection, query_id, user_id, page, limit, timeout):
    user = get_user_model().objects.get(id=user_id)

    user_connection_settings = get_user_explorer_connection_settings(
        user, query_connection
    )
    query_log = QueryLog.objects.create(
        sql=query_sql,
        query_id=query_id,
        run_by_user=user,
        connection=query_connection,
        page=page,
    )

    with user_explorer_connection(user_connection_settings) as conn:
        cursor = conn.cursor()

        start_time = time()
        sql = query_sql.rstrip().rstrip(';')

        table_name = tempory_query_table_name(user, query_log.id)
        try:
            cursor.execute(f'SET statement_timeout = {timeout}')
            # This is required to handle multiple select columns with the same name.
            # It adds a prefix of col_x_ to duplicated column returned from the query and
            # these prefixed column names are used to create a table containing the
            # query results. The prefixes are removed when the results are returned.
            cursor.execute(f'SELECT * FROM ({sql}) sq limit 0')
            column_names = list(zip(*cursor.description))[0]
            duplicated_column_names = set(
                c for c in column_names if column_names.count(c) > 1
            )
            prefixed_sql_columns = [
                (
                    f'"{_prefix_column(i, col[0]) if col[0] in duplicated_column_names else col[0]}" '
                    f'{TYPE_CODES_REVERSED[col[1]]}'
                )
                for i, col in enumerate(cursor.description, 1)
            ]

            cursor.execute(
                f'CREATE TABLE {table_name} ({", ".join(prefixed_sql_columns)})'
            )
            offset = ''
            if page and page > 1:
                offset = f' OFFSET {(page - 1) * limit}'

            cursor.execute(
                f'INSERT INTO {table_name} SELECT * FROM ({sql}) sq LIMIT {limit}{offset}'
            )
            cursor.execute(f'SELECT COUNT(*) FROM ({sql}) sq')
        except Exception as e:
            query_log.state = QueryLog.STATE_FAILED
            query_log.save()
            raise e

        row_count = cursor.fetchone()[0]
        duration = (time() - start_time) * 1000

        query_log.duration = duration
        query_log.rows = row_count
        query_log.state = QueryLog.STATE_COMPLETE
        query_log.save()

    logger.info("Created table %s and stored results", table_name)

    return query_log.id
