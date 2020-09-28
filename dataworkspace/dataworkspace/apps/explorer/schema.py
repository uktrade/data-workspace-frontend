import logging
from collections import namedtuple

from geoalchemy2 import Geometry  # Needed for sqlalchemy to understand geometry columns
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql.array import ARRAY
from sqlalchemy.dialects.postgresql.base import DOUBLE_PRECISION, ENUM, TIMESTAMP, UUID
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql.sqltypes import (
    BIGINT,
    BOOLEAN,
    CHAR,
    DATE,
    FLOAT,
    INTEGER,
    NUMERIC,
    SMALLINT,
    String,
    TEXT,
    VARCHAR,
)

from django.core.cache import cache

from dataworkspace.apps.explorer.app_settings import (
    EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES,
    EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES,
    EXPLORER_SCHEMA_INCLUDE_VIEWS,
)
from dataworkspace.apps.explorer.utils import get_user_explorer_connection_settings

logger = logging.getLogger(__name__)


# These wrappers make it easy to mock and test
def _get_includes():
    return EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES


def _get_excludes():
    return EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES


def _include_views():
    return EXPLORER_SCHEMA_INCLUDE_VIEWS is True


def _include_table(t):
    if _get_includes() is not None:
        return any([t.startswith(p) for p in _get_includes()])
    return not any([t.startswith(p) for p in _get_excludes()])


def connection_schema_cache_key(user, connection_alias):
    return f'_explorer_cache_key_{user.profile.sso_id}_{connection_alias}'


def schema_info(user, connection_alias, schema=None, table=None):
    key = connection_schema_cache_key(user, connection_alias)
    ret = cache.get(key)
    if ret:
        return ret

    ret = build_schema_info(user, connection_alias, schema, table)
    cache.set(key, ret)

    return ret


COLUMN_MAPPING = {
    ENUM: 'Enum',
    CHAR: 'Text',
    VARCHAR: 'Text',
    String: 'Text',
    TEXT: 'Text',
    UUID: 'UUID',
    ARRAY: 'Array',
    INTEGER: 'Integer',
    SMALLINT: 'Integer',
    BIGINT: 'Integer',
    NUMERIC: 'Decimal',
    DOUBLE_PRECISION: 'Decimal',
    FLOAT: 'Decimal',
    BOOLEAN: 'Boolean',
    DATE: 'Date',
    TIMESTAMP: 'Timestamp',
    Geometry: 'Geometry',
}

Column = namedtuple('Column', ['name', 'type'])
Table = namedtuple('Table', ['name', 'columns'])


class TableName(namedtuple("TableName", ['schema', 'name'])):
    __slots__ = ()

    def __str__(self):
        return f'{self.schema}.{self.name}'


def build_schema_info(user, connection_alias, schema=None, table=None):
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

    engine = create_engine(
        f'postgresql://{connection["db_user"]}:{connection["db_password"]}'
        f'@{connection["db_host"]}:{connection["db_port"]}/'
        f'{connection["db_name"]}'
    )

    insp = Inspector.from_engine(engine)
    if schema and table:
        return _get_columns_for_table(insp, schema, table)

    conn = engine.raw_connection()
    try:
        tables = []
        schemas_and_tables = _get_accessible_schemas_and_tables(conn)
        for schema_, table_name in schemas_and_tables:
            if not _include_table(table_name):
                continue

            columns = _get_columns_for_table(insp, schema_, table_name)
            tables.append(Table(TableName(schema_, table_name), columns))
    finally:
        conn.close()

    engine.dispose()
    return tables


def _get_accessible_schemas_and_tables(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema not in %s
ORDER BY table_schema, table_name;
""",
            [
                (
                    'pg_toast',
                    'pg_temp_1',
                    'pg_toast_temp_1',
                    'pg_catalog',
                    'information_schema',
                )
            ],
        )
        schemas_and_tables = cursor.fetchall()

    return schemas_and_tables


def _get_columns_for_table(insp, schema, table_name):
    columns = []
    cols = insp.get_columns(table_name, schema=schema)
    for col in cols:
        try:
            columns.append(Column(col['name'], COLUMN_MAPPING[type(col['type'])]))
        except KeyError:
            logger.info(
                'Skipping %s as %s (%s) is not a supported field type',
                col["name"],
                col["type"],
                type(col["type"]),
            )
            continue
    return columns
