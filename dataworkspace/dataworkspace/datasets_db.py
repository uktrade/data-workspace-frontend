import logging
from typing import List

import psycopg2
from django.db import connections

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

    with connections[database_name].cursor() as cursor:
        try:
            cursor.execute(
                psycopg2.sql.SQL('SELECT * from {} WHERE false').format(source)
            )
            return [c[0] for c in cursor.description]
        except Exception:  # pylint: disable=broad-except
            logger.error("Failed to get dataset fields", exc_info=True)
            return []


def get_tables_last_updated_date(database_name: str, tables: List[str]):
    """
    Return the earliest of the last updated dates for a list of tables.
    """
    with connections[database_name].cursor() as cursor:
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
                    MAX(source_data_modified_utc) run_date
                FROM dataflow.metadata
                WHERE CONCAT(metadata.table_schema, '.', metadata.table_name) = ANY(%s)
                GROUP BY 1
            ) a
            ''',
            [tables],
        )
        return cursor.fetchone()[0]
