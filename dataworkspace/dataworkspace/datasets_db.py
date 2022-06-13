from collections import defaultdict
import hashlib
import json
import logging
from typing import Tuple

import pglast
import psycopg2
from pglast.visitors import Visitor
from psycopg2.sql import Literal, SQL
import pytz
from django.conf import settings
from django.db import connections

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


def get_earliest_tables_last_updated_date(database_name: str, tables: Tuple[Tuple[str, str]]):
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


def get_all_tables_last_updated_date(tables: Tuple[Tuple[str, str, str]]):
    """
    Return the last updated dates in UTC for each table in a list of tables
    """

    def last_updated_date_for_database(database_name, tables_for_database: Tuple[Tuple[str, str]]):
        with connections[database_name].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    table_schema,
                    table_name,
                    MAX(source_data_modified_utc) AS modified_date,
                    MAX(dataflow_swapped_tables_utc) AS swap_table_date
                FROM dataflow.metadata
                WHERE (table_schema, table_name) IN %s
                GROUP BY (1, 2)
                """,
                [tuple(tables_for_database)],
            )
            return dict(
                (
                    (((table_schema, table_name), modified_date or swap_table_date))
                    for table_schema, table_name, modified_date, swap_table_date in cursor.fetchall()
                )
            )

    tables_by_database = defaultdict(list)
    for database_name, table_schema, table_name in tables:
        tables_by_database[database_name].append((table_schema, table_name))

    return {
        database_name: last_updated_date_for_database(database_name, tables_for_database)
        for database_name, tables_for_database in tables_by_database.items()
    }


class CustomRelationNames(Visitor):
    """
    Custom implementation of pglast's Visitor class that returns a schema/table tuple
    for a query
    """

    cte_names: set
    relation_names: set

    def __call__(self, node):
        self.cte_names = set()
        self.relation_names = set()
        super().__call__(node)
        relations = self.relation_names - self.cte_names
        return sorted(
            [(x[0] if x[0] is not None else "public", x[1]) for x in relations],
            key=lambda x: x[1],
        )

    def visit_CommonTableExpr(self, ancestors, node):
        # Add CTEs to be removed from the returned relations
        self.cte_names.add((None, node.ctename))

    def visit_RangeVar(self, ancestors, node):
        # Add relations to be returned
        relation_name = (None, node.relname)
        if node.schemaname:
            relation_name = (node.schemaname, node.relname)
        self.relation_names.add(relation_name)


def extract_queried_tables_from_sql_query(query):
    try:
        return CustomRelationNames()(pglast.parse_sql(query))
    except pglast.parser.ParseError:
        return []


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
    statements = pglast.parse_sql(sql)
    if statements[0].stmt()["sortClause"]:
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
