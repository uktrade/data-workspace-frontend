import threading
import time
from datetime import datetime, timedelta

import psycopg2
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connections, transaction
from pytz import utc

from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    close_admin_db_connection_if_not_in_atomic_block,
    close_all_connections_if_not_in_atomic_block,
    db_role_schema_suffix_for_user,
)
from dataworkspace.apps.explorer.constants import QueryLogState
from dataworkspace.apps.explorer.models import PlaygroundSQL, QueryLog
from dataworkspace.apps.explorer.utils import (
    get_user_explorer_connection_settings,
    tempory_query_table_name,
    user_explorer_connection,
)
from dataworkspace.cel import celery_app
from dataworkspace.settings.base import DATABASES_DATA
from dataworkspace.utils import TYPE_CODES_REVERSED

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
                output_table_schema, output_table_name = table_schema_and_name.split(".")
                cursor.execute(
                    psycopg2.sql.SQL("GRANT {role} TO {user}").format(
                        role=psycopg2.sql.Identifier(db_role),
                        user=psycopg2.sql.Identifier(server_db_user),
                    ),
                )
                cursor.execute(
                    psycopg2.sql.SQL("DROP TABLE IF EXISTS {table_schema_name}").format(
                        table_schema_name=psycopg2.sql.Identifier(
                            output_table_schema, output_table_name
                        )
                    )
                )
                cursor.execute(
                    psycopg2.sql.SQL("REVOKE {role} FROM {user}").format(
                        role=psycopg2.sql.Identifier(db_role),
                        user=psycopg2.sql.Identifier(server_db_user),
                    )
                )


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
    close_admin_db_connection_if_not_in_atomic_block()

    continue_polling = True

    with user_explorer_connection(user_connection_settings) as conn:

        @close_all_connections_if_not_in_atomic_block
        def poll():
            while True:
                if (
                    not continue_polling
                    or QueryLog.objects.filter(
                        id=query_log_id, state=QueryLogState.CANCELLED
                    ).exists()
                ):
                    break
                time.sleep(1)

            if QueryLog.objects.filter(id=query_log_id, state=QueryLogState.CANCELLED).exists():
                while continue_polling:
                    conn.cancel()
                    time.sleep(1)

        t = threading.Thread(target=poll)
        t.start()
        try:
            _run_query(
                conn,
                query_log,
                page,
                limit,
                timeout,
                tempory_query_table_name(query_log.run_by_user, query_log.id),
            )
        finally:
            continue_polling = False
            t.join()


def _run_query(conn, query_log, page, limit, timeout, output_table):
    cursor = conn.cursor()
    start_time = time.time()
    sql = query_log.sql.rstrip().rstrip(";")
    try:
        cursor.execute("SET statement_timeout = %s", (timeout,))

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
        cursor.execute(
            psycopg2.sql.SQL("SELECT * FROM ({user_query}) sq LIMIT 0").format(
                user_query=psycopg2.sql.SQL(sql)
            )
        )
        column_names = list(zip(*cursor.description))[0]
        duplicated_column_names = set(c for c in column_names if column_names.count(c) > 1)
        prefixed_sql_columns = [
            (
                f'"{_prefix_column(i, col[0]) if col[0] in duplicated_column_names else col[0]}" '
                f"{TYPE_CODES_REVERSED[col[1]]}"
            )
            for i, col in enumerate(cursor.description, 1)
        ]
        cols_formatted = ", ".join(prefixed_sql_columns)
        output_table_schema, output_table_name = output_table.split(".")
        cursor.execute(
            psycopg2.sql.SQL("CREATE TABLE {output_table} ({cols_formatted})").format(
                output_table=psycopg2.sql.Identifier(output_table_schema, output_table_name),
                cols_formatted=psycopg2.sql.SQL(cols_formatted),
            )
        )
        limit_clause = ""
        if limit is not None:
            limit_clause = f"LIMIT {limit}"

        offset = ""
        if page and page > 1 and limit is not None:
            offset = f" OFFSET {(page - 1) * limit}"

        cursor.execute(
            psycopg2.sql.SQL(
                "INSERT INTO {output_table} SELECT * FROM ({sql}) sq {limit_clause}{offset}"
            ).format(
                output_table=psycopg2.sql.Identifier(output_table_schema, output_table_name),
                sql=psycopg2.sql.SQL(sql),
                limit_clause=psycopg2.sql.SQL(limit_clause),
                offset=psycopg2.sql.SQL(offset),
            ),
        )
        cursor.execute(
            psycopg2.sql.SQL("SELECT COUNT(*) FROM ({sql}) sq").format(sql=psycopg2.sql.SQL(sql))
        )
    except psycopg2.errors.QueryCanceled as e:  # pylint: disable=no-member
        logger.info("Query cancelled: %s", e)
        return
    except (psycopg2.ProgrammingError, psycopg2.DataError) as e:
        _mark_query_log_failed(query_log, e)
        logger.warning("Failed to run query: %s", e)
        return
    except Exception as e:  # pylint: disable=broad-except
        _mark_query_log_failed(query_log, e)
        logger.exception("Failed to run query")
        return

    row_count = cursor.fetchone()[0]
    duration = (time.time() - start_time) * 1000

    try:
        with transaction.atomic():
            # This prevents the QueryLog from being marked as COMPLETE after it has been
            # marked as CANCELLED by the thread that gets spawned in _run_querylog_query
            query_log = QueryLog.objects.select_for_update().get(id=query_log.id)
            if query_log.state == QueryLogState.RUNNING:
                query_log.state = QueryLogState.COMPLETE

            query_log.duration = duration
            query_log.rows = row_count
            query_log.save()
    except IntegrityError as e:
        logger.error("Exception when marking QueryLog as COMPLETE: %s", e)

    logger.info("Created table %s and stored results", output_table)


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
