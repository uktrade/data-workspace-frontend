import logging
from typing import Tuple

import psycopg2
import pytz
from django.db import connections, transaction
from django.db.utils import DatabaseError

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
    Return the earliest of the last updated dates for a list of tables in UTC.
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
        dt = cursor.fetchone()[0]
        if dt is None:
            return None
        return dt.replace(tzinfo=pytz.UTC)


def extract_queried_tables_from_sql_query(database_name, query):
    # Extract the queried tables from the FROM clause using temporary views
    with connections[database_name].cursor() as cursor:
        try:
            with transaction.atomic():
                cursor.execute(
                    f"create temporary view get_tables as (select 1 from ({query.strip().rstrip(';')}) sq)"
                )
        except DatabaseError:
            tables = []
        else:
            cursor.execute(
                "select table_schema, table_name from information_schema.view_table_usage where view_name = 'get_tables'"
            )
            tables = cursor.fetchall()
            cursor.execute("drop view get_tables")

        return tables


def get_table_changelog(database_name: str, schema: str, table: str):
    """
    Fetch a list of distinct changes to a datasets db table
    """
    with connections[database_name].cursor() as cursor:
        cursor.execute(
            '''
            SELECT
                MIN(source_data_modified_utc) change_date,
                table_structure,
                'Table structure updated' change_type
            FROM dataflow.metadata
            WHERE table_schema = %s
            AND table_name = %s
            GROUP BY table_structure
            ORDER BY change_date DESC;
            ''',
            [schema, table],
        )
        columns = [x.name for x in cursor.description]
        records = []
        for row in cursor.fetchall():
            record = {}
            for idx, field in enumerate(row):
                record[columns[idx]] = field
            record['change_date'] = record['change_date'].replace(tzinfo=pytz.UTC)
            records.append(record)
        return records


def get_custom_dataset_query_changelog(database_name: str, query):
    with connections[database_name].cursor() as cursor:
        cursor.execute(
            '''
            SELECT
                MIN(source_data_modified_utc) change_date,
                table_structure,
                'Table structure updated' change_type
            FROM dataflow.metadata
            WHERE data_id = %s
            GROUP BY table_structure
            ORDER BY change_date DESC;
            ''',
            [query.id],
        )
        columns = [x.name for x in cursor.description]
        records = []
        for row in cursor.fetchall():
            record = {}
            for idx, field in enumerate(row):
                record[columns[idx]] = field
            record['change_date'] = record['change_date'].replace(tzinfo=pytz.UTC)
            records.append(record)
        return records
