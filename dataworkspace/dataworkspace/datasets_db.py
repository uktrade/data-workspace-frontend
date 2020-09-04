import logging
from typing import List

import psycopg2
from django.conf import settings

from dataworkspace.apps.core.utils import database_dsn

logger = logging.getLogger('app')


def get_columns(database_name, schema=None, table=None, query=None):
    if table is not None and schema is not None:
        source = psycopg2.sql.SQL("{}.{}").format(
            psycopg2.sql.Identifier(schema), psycopg2.sql.Identifier(table)
        )
    elif query is not None:
        source = psycopg2.sql.SQL("({}) AS custom_query".format(query.rstrip(";")))
    else:
        raise ValueError("Either table or query are required")

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[database_name])
    ) as connection:
        try:
            return query_columns(connection, source)
        except Exception:  # pylint: disable=broad-except
            logger.error("Failed to get dataset fields", exc_info=True)
            return []


def query_columns(connection, source):
    sql = psycopg2.sql.SQL('SELECT * from {} WHERE false').format(source)
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [c[0] for c in cursor.description]


def get_tables_last_updated_date(database_name: str, tables: List[str]):
    """
    Return the earliest of the last updated dates for a list of tables.
    """
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[database_name])
    ) as connection, connection.cursor() as cursor:
        # Check the metadata table exists before we query it
        cursor.execute("SELECT to_regclass('dataflow.metadata')")
        if cursor.fetchone()[0] != 'dataflow.metadata':
            return None

        cursor.execute(
            '''
            SELECT MIN(run_date)
            FROM (
                SELECT
                    CONCAT(metadata.table_schema, '.', metadata.table_name),
                    MAX(dataflow_swapped_tables_utc) run_date
                FROM dataflow.metadata
                WHERE CONCAT(metadata.table_schema, '.', metadata.table_name) = ANY(%s)
                GROUP BY 1
            ) a
            ''',
            [tables],
        )
        return cursor.fetchone()[0]
