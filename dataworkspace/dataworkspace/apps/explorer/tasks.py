from datetime import datetime, timedelta
from time import time

import psycopg2
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections

from pytz import utc

from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    close_all_connections_if_not_in_atomic_block,
    database_dsn,
    db_role_schema_suffix_for_user,
)
from dataworkspace.apps.explorer.constants import QueryLogState
from dataworkspace.apps.explorer.models import ChartBuilderChart, QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.utils import (
    get_user_explorer_connection_settings,
    tempory_query_table_name,
    user_explorer_connection,
)
from dataworkspace.utils import TYPE_CODES_REVERSED
from dataworkspace.cel import celery_app
from dataworkspace.settings.base import DATABASES_DATA

logger = get_task_logger(__name__)


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def truncate_querylogs(days):
    qs = QueryLog.objects.filter(run_at__lt=datetime.now() - timedelta(days=days))
    logger.info("Deleting %s QueryLog objects older than %s days.", qs.count, days)
    qs.delete()
    logger.info("Done deleting QueryLog objects.")


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
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
@close_all_connections_if_not_in_atomic_block
def cleanup_temporary_query_tables():
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    logger.info("Cleaning up Data Explorer temporary query tables older than %s", one_day_ago)

    for query_log in QueryLog.objects.filter(run_at__lte=one_day_ago):
        server_db_user = DATABASES_DATA[query_log.connection]["USER"]
        db_role = f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(query_log.run_by_user)}"
        table_schema_and_name = tempory_query_table_name(query_log.run_by_user, query_log.id)

        with cache.lock(
            f'database-grant--{DATABASES_DATA[query_log.connection]["NAME"]}--{db_role}--v4',
            blocking_timeout=3,
            timeout=180,
        ):
            with connections[query_log.connection].cursor() as cursor:
                logger.info("Dropping temporary query table %s", table_schema_and_name)
                cursor.execute(f"GRANT {db_role} TO {server_db_user}")
                cursor.execute(f"DROP TABLE IF EXISTS {table_schema_and_name}")
                cursor.execute(f"REVOKE {db_role} FROM {server_db_user}")


def _prefix_column(index, column):
    return f"col_{index}_{column}"


def _mark_query_log_failed(query_log, exc):
    # Remove the select statement wrapper used for getting the query fields
    query_log.error = str(exc).replace("SELECT * FROM (", "").replace(") sq LIMIT 0", "")
    query_log.state = QueryLogState.FAILED
    query_log.save()


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def _run_querylog_query(query_log_id, page, limit, timeout):
    query_log = QueryLog.objects.get(id=query_log_id)
    user_connection_settings = get_user_explorer_connection_settings(
        query_log.run_by_user, query_log.connection
    )
    with user_explorer_connection(user_connection_settings) as conn:
        _run_query(
            conn,
            query_log,
            page,
            limit,
            timeout,
            tempory_query_table_name(query_log.run_by_user, query_log.id),
        )


def _run_query(conn, query_log, page, limit, timeout, output_table):
    cursor = conn.cursor()
    start_time = time()
    sql = query_log.sql.rstrip().rstrip(";")

    try:
        cursor.execute(f"SET statement_timeout = {timeout}")
        if sql.strip().upper().startswith("EXPLAIN"):
            cursor.execute(
                """
                create or replace function query_plan(in qry text) returns setof text as $$
                declare r text;
                BEGIN
                FOR r IN EXECUTE qry loop
                    return next r;
                END LOOP;
                return;
                END; $$ language plpgsql;
                """
            )
            sql = sql.replace("'", "''")
            sql = f"select query_plan('{sql}')"
        # This is required to handle multiple select columns with the same name.
        # It adds a prefix of col_x_ to duplicated column returned from the query and
        # these prefixed column names are used to create a table containing the
        # query results. The prefixes are removed when the results are returned.
        cursor.execute(f"SELECT * FROM ({sql}) sq LIMIT 0")
        column_names = list(zip(*cursor.description))[0]
        duplicated_column_names = set(c for c in column_names if column_names.count(c) > 1)
        prefixed_sql_columns = [
            (
                f'"{_prefix_column(i, col[0]) if col[0] in duplicated_column_names else col[0]}" '
                f"{TYPE_CODES_REVERSED[col[1]]}"
            )
            for i, col in enumerate(cursor.description, 1)
        ]
        cursor.execute(f'CREATE TABLE {output_table} ({", ".join(prefixed_sql_columns)})')

        limit_clause = ""
        if limit is not None:
            limit_clause = f"LIMIT {limit}"

        offset = ""
        if page and page > 1 and limit is not None:
            offset = f" OFFSET {(page - 1) * limit}"

        cursor.execute(
            f"INSERT INTO {output_table} SELECT * FROM ({sql}) sq {limit_clause}{offset}"
        )
        cursor.execute(f"SELECT COUNT(*) FROM ({sql}) sq")
    except (psycopg2.ProgrammingError, psycopg2.DataError) as e:
        _mark_query_log_failed(query_log, e)
        logger.warning("Failed to run query: %s", e)
        return
    except Exception as e:  # pylint: disable=broad-except
        _mark_query_log_failed(query_log, e)
        logger.exception("Failed to run query")
        return

    row_count = cursor.fetchone()[0]
    duration = (time() - start_time) * 1000

    query_log.duration = duration
    query_log.rows = row_count
    query_log.state = QueryLogState.COMPLETE
    query_log.save()

    logger.info("Created table %s and stored results", output_table)


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def run_chart_builder_query(chart_id):
    chart = ChartBuilderChart.objects.get(id=chart_id)
    query_log = chart.query_log
    with psycopg2.connect(database_dsn(DATABASES_DATA[query_log.connection])) as conn:
        _run_query(
            conn,
            query_log,
            query_log.page,
            query_log.page_size,
            settings.EXPLORER_QUERY_TIMEOUT_MS,
            chart.get_temp_table_name(),
        )


def submit_query_for_execution(
    query_sql, query_connection, query_id, user_id, page, limit, timeout
):
    user = get_user_model().objects.get(id=user_id)
    query_log = QueryLog.objects.create(
        sql=query_sql,
        query_id=query_id,
        run_by_user=user,
        connection=query_connection,
        page=page,
        page_size=limit,
    )

    _run_querylog_query.delay(query_log.id, page, limit, timeout)

    return query_log


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def refresh_chart_thumbnail(chart_id):
    ChartBuilderChart.objects.get(id=chart_id).refresh_thumbnail()


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def refresh_published_chart_data():
    for chart in ChartBuilderChart.objects.filter(datasets__isnull=False):
        original_query_log = chart.query_log
        original_table_name = chart.get_temp_table_name()
        chart.query_log = QueryLog.objects.create(
            sql=original_query_log.sql,
            query_id=original_query_log.query_id,
            run_by_user=chart.created_by,
            connection=original_query_log.connection,
            page=1,
            page_size=None,
        )
        chart.save()
        run_chart_builder_query(chart.id)
        chart.refresh_thumbnail()
        with psycopg2.connect(database_dsn(DATABASES_DATA[original_query_log.connection])) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {original_table_name}")
