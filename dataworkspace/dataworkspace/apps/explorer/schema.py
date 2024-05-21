import datetime
import logging
import time
from collections import namedtuple
from itertools import groupby

import psycopg2
from psycopg2.extras import RealDictCursor

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Func, Value

from dataworkspace.apps.explorer.connections import connections
from dataworkspace.apps.explorer.utils import get_user_explorer_connection_settings
from dataworkspace.apps.datasets.models import SourceTable, ReferenceDataset

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
        logger.info("Returning cached schema information for user %s", user.email)
        return ret

    logger.info("Building schema information for user %s", user.email)
    start_time = time.time()
    ret = build_schema_info(user, connection_alias)
    logger.info(
        "Building schema information for user %s took %s seconds",
        user.email,
        round(time.time() - start_time, 2),
    )
    cache.set(key, ret, timeout=datetime.timedelta(days=7).total_seconds())

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
        # Fetch schema, table, column_name, column_type in one query, based on
        # https://dba.stackexchange.com/a/339630/37229 to get parent roles and
        # https://stackoverflow.com/a/78466268/1319998 to get their permissions
        # By using pg_shdepend this avoids full table scans and is usually much faster than using
        # information_schema or has_schema_privilege/has_table_privilege functions when there are
        # many tables in the database. This is similar to the techniques used in
        # https://github.com/uktrade/pg-sync-roles
        cursor.execute(
            """
            WITH

            -- The current user's roleid, and all roles that the current user inherits permissions from
            RECURSIVE granted_roles AS (
                SELECT r.oid, r.rolinherit
                FROM pg_roles r
                WHERE rolname = CURRENT_USER
              UNION
                SELECT r.oid, r.rolinherit
                FROM granted_roles g
                INNER JOIN pg_auth_members m ON m.member = g.oid
                INNER JOIN pg_roles r ON r.oid = m.roleid
                WHERE g.rolinherit = TRUE -- Do not walk up tree beyond NOINHERIT
            ),

            -- Tables and schemas that the current user + its roles might have permissions on
            -- There will be no permissions in the case that roles are just owner with no other perms,
            -- but we won't know that until we look to pg_namespace or pg_class below
            objects_with_maybe_privileges AS (
              SELECT
                refobjid,  -- The referenced object: the role in this case
                classid,   -- The pg_class oid that the dependant object is in
                objid      -- The oid of the dependant object in the table specified by classid
              FROM pg_shdepend
              INNER JOIN granted_roles r ON r.oid = refobjid
              WHERE refclassid='pg_catalog.pg_authid'::regclass
                AND deptype IN ('a', 'o')
                AND classid IN ('pg_namespace'::regclass, 'pg_class'::regclass)
                AND dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                AND objsubid = 0  -- Non-zero only for table-column permissions
            ),

            -- Schemas where at least one role has USAGE
            schemas_with_usage AS (
              SELECT DISTINCT n.oid, nspname
              FROM pg_namespace n
              INNER JOIN objects_with_maybe_privileges a ON a.objid = n.oid
              CROSS JOIN aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner)))
              WHERE classid = 'pg_namespace'::regclass
                AND grantee = refobjid
                AND privilege_type = 'USAGE'
            ),

            -- Tables where at least one role has SELECT, and where a role also has USAGE on its schema
            tables_with_select_in_schemas_with_usage AS (
              SELECT DISTINCT nspname, relname, c.oid
              FROM pg_class c
              INNER JOIN schemas_with_usage n ON n.oid = c.relnamespace
              INNER JOIN objects_with_maybe_privileges a ON a.objid = c.oid
              CROSS JOIN aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner)))
              WHERE classid = 'pg_class'::regclass
                AND grantee = refobjid
                AND privilege_type = 'SELECT'
                AND relkind IN ('r', 'v', 'm', 'f', 'p') -- All real table-like things
                AND relname NOT SIMILAR TO '\\_data\\_explorer\\_tmp\\_%|%\\_swap'
            )

            -- All the columns on all the tables above
            SELECT
              nspname AS schema_name,
              relname AS table_name,
              attname AS column_name,
              pg_catalog.format_type(atttypid, atttypmod) AS column_type
            FROM tables_with_select_in_schemas_with_usage t
            INNER JOIN pg_attribute ON attrelid = t.oid
            WHERE attnum > 0
            ORDER BY nspname, relname, attnum
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
    start_time = time.time()
    # For each table in schema, find if the corresponding SourceTable has its dictionary_published
    schema_table_names = [
        Func(Value(s.name.schema), Value(s.name.name), function="Row") for s in schema
    ]

    # reference_code is not needed, but we included it here since DataSet's __init__ class
    # uses it and so results in a query per DataSet if we don't
    source_tables = (
        SourceTable.objects.alias(schema_table=Func(F("schema"), F("table"), function="Row"))
        .filter(schema_table__in=schema_table_names)
        .only("schema", "table", "dataset__dictionary_published")
        .values("schema", "table", "dataset__dictionary_published")
    )

    # Attach the dictionary_published to each table in schema
    dictionary_published = {
        (source_table["schema"], source_table["table"]): source_table[
            "dataset__dictionary_published"
        ]
        for source_table in source_tables
    }

    # Same logic for reference datasets
    reference_datasets = ReferenceDataset.objects.filter(
        table_name__in=[
            s.name.name
            for s in schema
            if s.name.schema == "public" and s.name.name.startswith("ref_")
        ]
    ).values("table_name")

    for dataset in reference_datasets:
        dictionary_published[("public", dataset["table_name"])] = True

    for s in schema:
        s.name.dictionary_published = dictionary_published.get((s.name.schema, s.name.name), False)
    logger.info(
        "match_datasets_with_schema_info: schema matching took %s seconds",
        round(time.time() - start_time, 2),
    )
    return schema
