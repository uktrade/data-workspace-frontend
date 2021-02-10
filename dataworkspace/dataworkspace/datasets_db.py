import logging
from typing import Tuple

import psycopg2
from django.db import connections

from dataworkspace.utils import TYPE_CODES_REVERSED

logger = logging.getLogger('app')


def get_columns(
    database_name, schema=None, table=None, query=None, include_types=False
):
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

            if include_types:
                return [
                    (c[0], TYPE_CODES_REVERSED.get(c[1], "Unknown"))
                    for c in cursor.description
                ]

            return [c[0] for c in cursor.description]
        except Exception:  # pylint: disable=broad-except
            logger.error("Failed to get dataset fields", exc_info=True)
            return []


def get_tables_last_updated_date(database_name: str, tables: Tuple[Tuple[str, str]]):
    """
    Return the earliest of the last updated dates for a list of tables.
    """
    with connections[database_name].cursor() as cursor:
        cursor.execute(
            '''
            SELECT MIN(modified_date)
            FROM (
                SELECT
                    table_schema,
                    table_name,
                    MAX(source_data_modified_utc) AS modified_date
                FROM dataflow.metadata
                WHERE (table_schema, table_name) IN %s
                GROUP BY (1, 2)
            ) a
            ''',
            [tables],
        )
        return cursor.fetchone()[0]
