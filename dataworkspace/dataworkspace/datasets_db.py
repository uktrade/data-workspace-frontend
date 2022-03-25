import hashlib
import json
import logging
from typing import Tuple

import psqlparse
import psycopg2
from psycopg2.sql import Literal, SQL
import pytz
from django.conf import settings
from django.db import connections, transaction
from django.db.utils import DatabaseError

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.utils import TYPE_CODES_REVERSED

logger = logging.getLogger("app")


def get_columns(database_name, schema=None, table=None, query=None, include_types=False):
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
            cursor.execute(psycopg2.sql.SQL("SELECT * from {} WHERE false").format(source))

            if include_types:
                return [
                    (c[0], TYPE_CODES_REVERSED.get(c[1], "Unknown")) for c in cursor.description
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
            """
            SELECT MIN(modified_date),MIN(swap_table_date)
            FROM (
                SELECT
                    table_schema,
                    table_name,
                    MAX(source_data_modified_utc) AS modified_date,
                    MAX(dataflow_swapped_tables_utc) AS swap_table_date
                FROM dataflow.metadata
                WHERE (table_schema, table_name) IN %s
                AND data_type != %s
                GROUP BY (1, 2)
            ) a
            """,
            [tables, DataSetType.REFERENCE],
        )
        modified_date, swap_table_date = cursor.fetchone()
        dt = modified_date or swap_table_date
        return dt.replace(tzinfo=pytz.UTC) if dt else None


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


def get_source_table_changelog(source_table):
    with connections[source_table.database.memorable_name].cursor() as cursor:
        cursor.execute(
            SQL(
                """
                SELECT id, source_data_modified_utc, table_schema||'.'||table_name, table_structure, data_hash_v1
                FROM dataflow.metadata
                WHERE data_type = {}
                AND {} = any(data_ids)
                AND source_data_modified_utc IS NOT NULL
                AND table_structure IS NOT NULL
                ORDER BY id ASC;
                """
            ).format(
                Literal(DataSetType.MASTER),
                Literal(str(source_table.id)),
            )
        )
        return get_changelog_from_metadata_rows(cursor.fetchall())


def get_custom_dataset_query_changelog(query):
    with connections[query.database.memorable_name].cursor() as cursor:
        cursor.execute(
            SQL(
                """
                SELECT id, source_data_modified_utc, table_schema||'.'||table_name, table_structure, data_hash_v1
                FROM dataflow.metadata
                WHERE data_type = {}
                AND {} = any(data_ids)
                AND source_data_modified_utc IS NOT NULL
                AND table_structure IS NOT NULL
                ORDER BY id ASC;
                """
            ).format(
                Literal(DataSetType.DATACUT),
                Literal(str(query.id)),
            )
        )
        return get_changelog_from_metadata_rows(cursor.fetchall())


def get_reference_dataset_changelog(dataset):
    db_name = list(settings.DATABASES_DATA.items())[0][0]
    with connections[db_name].cursor() as cursor:
        cursor.execute(
            SQL(
                """
                SELECT id, source_data_modified_utc, table_schema||'.'||table_name, table_structure, data_hash_v1
                FROM dataflow.metadata
                WHERE data_type = {}
                AND {} = any(data_ids)
                AND source_data_modified_utc IS NOT NULL
                AND table_structure IS NOT NULL
                ORDER BY id ASC;
                """
            ).format(
                Literal(DataSetType.REFERENCE),
                Literal(str(dataset.id)),
            )
        )
        return get_changelog_from_metadata_rows(cursor.fetchall())


def get_data_hash(cursor, sql):
    statements = psqlparse.parse(sql)
    if statements[0].sort_clause:
        hashed_data = hashlib.md5()
        cursor.execute(SQL(f"SELECT t.*::TEXT FROM ({sql}) as t"))
        for row in cursor:
            hashed_data.update(row[0].encode("utf-8"))
        return hashed_data.digest()
    return None


def get_changelog_from_metadata_rows(rows):
    if not rows:
        return []

    # Always add the first row to the change log
    changelog = [
        {
            "change_id": rows[0][0],
            "change_date": rows[0][1].replace(tzinfo=pytz.UTC),
            "table_name": rows[0][2],
            "previous_table_name": None,
            "table_structure": json.loads(rows[0][3]) if rows[0][3] else None,
            "previous_table_structure": None,
            "data_hash": rows[0][4],
            "previous_data_hash": None,
        }
    ]

    #  zip(rows, rows[1:]): [1,2,3,4,5] --> [(1,2), (2,3), (3,4), (4,5)]
    for row, next_row in zip(rows, rows[1:]):
        _, _, row_table_name, row_table_structure, row_data_hash = row
        (
            next_row_id,
            next_row_change_date,
            next_row_table_name,
            next_row_table_structure,
            next_row_data_hash,
        ) = next_row
        if (
            row_table_structure != next_row_table_structure
            or row_data_hash != next_row_data_hash
            or row_table_name != next_row_table_name
        ):
            changelog.append(
                {
                    "change_id": next_row_id,
                    "change_date": next_row_change_date.replace(tzinfo=pytz.UTC),
                    "table_name": next_row_table_name,
                    "previous_table_name": row_table_name,
                    "table_structure": json.loads(next_row_table_structure)
                    if next_row_table_structure
                    else None,
                    "previous_table_structure": json.loads(row_table_structure)
                    if row_table_structure
                    else None,
                    "data_hash": next_row_data_hash,
                    "previous_data_hash": row_data_hash,
                }
            )

    return list(reversed(changelog))
