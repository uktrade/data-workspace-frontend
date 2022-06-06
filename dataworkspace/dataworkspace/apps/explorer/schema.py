import logging
from collections import namedtuple
from itertools import groupby

import psycopg2
from psycopg2.extras import RealDictCursor

from django.conf import settings
from django.core.cache import cache

from dataworkspace.apps.explorer.connections import connections
from dataworkspace.apps.explorer.utils import get_user_explorer_connection_settings
from dataworkspace.apps.datasets.models import SourceTable

logger = logging.getLogger(__name__)


# These wrappers make it easy to mock and test
def _get_includes():
    return settings.EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES


def _get_excludes():
    return settings.EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES


def _include_table(t):
    # pylint: disable=use-a-generator
    if _get_includes() is not None:
        return any([t.startswith(p) for p in _get_includes()])
    return not any([t.startswith(p) for p in _get_excludes()])


def connection_schema_cache_key(user, connection_alias):
    return f"_explorer_cache_key_{user.profile.sso_id}_{connection_alias}"


def schema_info(user, connection_alias):
    key = connection_schema_cache_key(user, connection_alias)
    ret = cache.get(key)
    if ret:
        return ret

    ret = build_schema_info(user, connection_alias)
    cache.set(key, ret)

    return ret


def clear_schema_info_cache_for_user(user):
    for connection in connections.values():
        cache.delete(connection_schema_cache_key(user, connection))


Column = namedtuple("Column", ["name", "type"])
Table = namedtuple("Table", ["name", "columns"])


class TableName(namedtuple("TableName", ["schema", "name"])):

    dictionary_published = False

    def __str__(self):
        return f"{self.schema}.{self.name}"


def build_schema_info(user, connection_alias):
    """
    Construct schema information via engine-specific queries of the tables in the DB.

    :return: Schema information of the following form.
        [
            (("db_schema_name", "db_table_name"),
                [
                    ("db_column_name", "DbFieldType"),
                    (...),
                ]
            )
        ]

    """

    connection = get_user_explorer_connection_settings(user, connection_alias)
    with psycopg2.connect(
        f'postgresql://{connection["db_user"]}:{connection["db_password"]}'
        f'@{connection["db_host"]}:{connection["db_port"]}/'
        f'{connection["db_name"]}'
    ) as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Fetch schema, table, column_name, column_type in one query, avoiding
        # information_schema since there is suspicion it is slow
        cursor.execute(
            """
            SELECT
              pg_namespace.nspname AS schema_name,
              pg_class.relname AS table_name,
              pg_attribute.attname AS column_name,
              pg_catalog.format_type(atttypid, atttypmod) AS column_type
            FROM
              pg_attribute
              INNER JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
              INNER JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
            WHERE
              pg_namespace.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast') AND
              pg_namespace.nspname NOT SIMILAR TO 'pg_temp_%|pg_toast_temp_%' AND
              pg_class.relname NOT SIMILAR TO '%_swap|%_idx' AND
              has_schema_privilege(pg_namespace.nspname, 'USAGE') AND
              has_table_privilege(
                quote_ident(pg_namespace.nspname) || '.' || quote_ident(pg_class.relname),
                'SELECT'
              ) = true AND
              attnum > 0
            ORDER BY
              pg_namespace.nspname, pg_class.relname, attnum
        """
        )
        results = [row for row in cursor.fetchall() if _include_table(row["table_name"])]

    return [
        Table(
            TableName(schema_name, table_name),
            [Column(column["column_name"], column["column_type"]) for column in columns],
        )
        for (schema_name, table_name), columns in groupby(
            results, lambda row: (row["schema_name"], row["table_name"])
        )
    ]


def get_user_schema_info(request):
    schema = schema_info(user=request.user, connection_alias=settings.EXPLORER_DEFAULT_CONNECTION)
    tables_columns = [".".join(schema_table) for schema_table, _ in schema]
    return schema, tables_columns


def match_datasets_with_schema_info(schema):
    for s in schema:
        query = SourceTable.objects.filter(schema=s.name.schema, table=s.name.name)
        if query.exists():
            s.name.dictionary_published = query.first().dataset.dictionary_published
    return schema
