import datetime
import json
import os
from functools import wraps
import hashlib
import itertools
import logging
import random
import re
import secrets
import string
import csv
from io import StringIO
from typing import Tuple

from timeit import default_timer as timer
from urllib.parse import unquote

import gevent
import gevent.queue

import psycopg2
import requests
from mohawk import Sender
from psycopg2 import connect, sql
from psycopg2.sql import SQL


from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import StreamingHttpResponse
from django.db import connections, connection
from django.db.models import Q
from django.conf import settings
from tableschema import Schema

from dataworkspace.apps.core.boto3_client import get_s3_client, get_iam_client
from dataworkspace.apps.core.constants import (
    DATA_FLOW_TASK_ERROR_MAP,
    PostgresDataTypes,
    SCHEMA_POSTGRES_DATA_TYPE_MAP,
    TABLESCHEMA_FIELD_TYPE_MAP,
)
from dataworkspace.apps.core.models import Database, DatabaseUser, Team
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import DataSet, SourceTable, ReferenceDataset

logger = logging.getLogger("app")

USER_SCHEMA_STEM = "_user_"


def database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} '
        f'dbname={database_data["NAME"]} user={database_data["USER"]} '
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def postgres_user(stem, suffix=""):
    if len(suffix) > 10:
        raise ValueError(
            "The user suffix should be no more than 10 characters to ensure that the stem "
            "doesn't get truncated too severely."
        )

    user_alphabet = string.ascii_lowercase + string.digits
    unique_enough = "".join(secrets.choice(user_alphabet) for i in range(5))
    suffix = f"_{suffix}" if suffix else ""

    # Postgres identifiers can be up to 63 characters.
    # Between `user_`, `_`, and `unique_enough` we use 11 of these characters.
    # This leaves 52 characters for the email and suffix parts.
    # So let's truncate the email address based on the remaining characters we have available.
    max_email_length = 52 - len(suffix)

    return (
        "user_"
        + re.sub("[^a-z0-9]", "_", stem.lower())[:max_email_length]
        + "_"
        + unique_enough
        + suffix
    )


def db_role_schema_suffix_for_user(user):
    return stable_identification_suffix(str(user.profile.sso_id), short=True)


def db_role_schema_suffix_for_app(application_template):
    return "app_" + application_template.host_basename


def new_private_database_credentials(
    db_role_and_schema_suffix,
    source_tables,
    db_user,
    dw_user: get_user_model(),
    valid_for: datetime.timedelta,
    force_create_for_databases: Tuple[Database] = tuple(),
):
    db_team_roles = [team.schema_name for team in Team.objects.filter(member=dw_user)]
    db_team_roles_set = set(db_team_roles)
    db_team_schemas = db_team_roles

    # This function can take a while. That isn't great, but also not great to
    # hold a connection to the admin database
    close_admin_db_connection_if_not_in_atomic_block()

    password_alphabet = string.ascii_letters + string.digits

    def postgres_password():
        return "".join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, tables):
        # Each real-world user is given
        # - a private and permanent schema where they can manage tables and rows as needed
        # - a permanent database role that is the owner of the schema
        # - temporary database users, each of which are GRANTed the role

        db_password = postgres_password()
        db_role = f"{USER_SCHEMA_STEM}{db_role_and_schema_suffix}"
        db_schema = f"{USER_SCHEMA_STEM}{db_role_and_schema_suffix}"

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.datetime.now() + valid_for).isoformat()

        with connections[database_obj.memorable_name].cursor() as cur:
            existing_tables_and_views_set = set(tables_and_views_that_exist(cur, tables))

            allowed_tables_that_exist = [
                (schema, table)
                for schema, table in tables
                if (schema, table) in existing_tables_and_views_set
            ]
            allowed_tables_that_exist_set = set(allowed_tables_that_exist)

            allowed_schemas_that_exist = without_duplicates_preserve_order(
                schema for schema, _ in allowed_tables_that_exist
            )
            allowed_schemas_that_exist_set = set(allowed_schemas_that_exist)

            def ensure_db_role(db_role_name):
                cur.execute(
                    sql.SQL(
                        """
                    DO $$
                    BEGIN
                      CREATE ROLE {role};
                    EXCEPTION WHEN OTHERS THEN
                      RAISE DEBUG 'Role {role} already exists';
                    END
                    $$;
                """
                    ).format(role=sql.Identifier(db_role_name))
                )

            for db_role_name in db_team_roles + [db_role]:
                ensure_db_role(db_role_name)

            # On RDS, to do SET ROLE, you have to GRANT the role to the current master user. You also
            # have to have (at least) USAGE on each user schema to call has_table_privilege. So,
            # we make sure the master user has this before the user schema is even created. But, since
            # this would involve a GRANT, and since GRANTs have to be wrapped in the lock, we check if
            # we need to do it first
            cur.execute(
                sql.SQL(
                    """
                SELECT
                    rolname
                FROM
                    pg_roles
                WHERE
                    (
                        rolname SIMILAR TO '\\_user\\_[0-9a-f]{8}' OR
                        rolname LIKE '\\_user\\_app\\_%' OR
                        rolname LIKE '\\_team\\_%'
                    )
                    AND NOT pg_has_role(rolname, 'member');
            """
                )
            )
            missing_db_roles = [role for (role,) in cur.fetchall()]

        if missing_db_roles:
            with cache.lock(
                "database-grant-v1",
                blocking_timeout=15,
                timeout=60,
            ), connections[database_obj.memorable_name].cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT {} TO {};").format(
                        sql.SQL(",").join(
                            sql.Identifier(missing_db_role) for missing_db_role in missing_db_roles
                        ),
                        sql.Identifier(database_data["USER"]),
                    )
                )

        with connections[database_obj.memorable_name].cursor() as cur:
            # Find existing permissions
            cur.execute(
                sql.SQL(
                    """
                SELECT
                    schemaname AS schema,
                    tablename as name
                FROM
                    pg_catalog.pg_tables
                WHERE
                    schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast', {schema})
                    AND schemaname NOT LIKE 'pg_temp_%'
                    AND schemaname NOT LIKE 'pg_toast_temp_%'
                    AND schemaname NOT LIKE '_team_%'
                    AND tablename !~ '_\\d{{8}}t\\d{{6}}'
                    AND has_table_privilege({role}, quote_ident(schemaname) || '.' ||
                        quote_ident(tablename), 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER') = true
                UNION ALL
                SELECT
                    schemaname AS schema,
                    viewname as name
                FROM
                    pg_catalog.pg_views
                WHERE
                    schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast', {schema})
                    AND schemaname NOT LIKE 'pg_temp_%'
                    AND schemaname NOT LIKE 'pg_toast_temp_%'
                    AND schemaname NOT LIKE '_team_%'
                    AND has_table_privilege({role}, quote_ident(schemaname) || '.' ||
                        quote_ident(viewname), 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
                UNION ALL
                SELECT
                    schemaname AS schema,
                    matviewname as name
                FROM
                    pg_catalog.pg_matviews
                WHERE
                    schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast', {schema})
                    AND schemaname NOT LIKE 'pg_temp_%'
                    AND schemaname NOT LIKE 'pg_toast_temp_%'
                    AND schemaname NOT LIKE '_team_%'
                    AND has_table_privilege({role}, quote_ident(schemaname) || '.' ||
                        quote_ident(matviewname), 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER') = true
                ORDER BY schema, name;
            """
                ).format(role=sql.Literal(db_role), schema=sql.Literal(db_schema))
            )
            tables_with_existing_privs = cur.fetchall()
            tables_with_existing_privs_set = set(tables_with_existing_privs)

            cur.execute(
                sql.SQL(
                    """
                SELECT
                    nspname AS name
                FROM
                    pg_namespace
                WHERE
                    nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast', {schema})
                    AND nspname NOT LIKE 'pg_temp_%'
                    AND nspname NOT LIKE 'pg_toast_temp_%'
                    AND has_schema_privilege({role}, nspname, 'CREATE, USAGE')
                ORDER BY nspname;
            """
                ).format(role=sql.Literal(db_role), schema=sql.Literal(db_schema))
            )
            schemas_with_existing_privs = [row[0] for row in cur.fetchall()]
            schemas_with_existing_privs_set = set(schemas_with_existing_privs)

            # Existing granted team roles to permanant user role
            cur.execute(
                sql.SQL(
                    """
                SELECT
                    rolname
                FROM
                    pg_roles
                WHERE
                    (
                        rolname LIKE '\\_team\\_'
                    )
                    AND pg_has_role({db_role}, rolname, 'member');
            """
                ).format(db_role=sql.Literal(db_role))
            )
            db_team_roles_previously_granted = [role for (role,) in cur.fetchall()]
            db_team_roles_previously_granted_set = set(db_team_roles_previously_granted)

            tables_to_revoke = [
                (schema, table)
                for (schema, table) in tables_with_existing_privs
                if (schema, table) not in allowed_tables_that_exist_set
            ]
            tables_to_grant = [
                (schema, table)
                for (schema, table) in allowed_tables_that_exist
                if (schema, table) not in tables_with_existing_privs_set
            ]

            schemas_to_revoke = [
                schema
                for schema in schemas_with_existing_privs
                if schema not in allowed_schemas_that_exist_set
            ]
            schemas_to_grant = [
                schema
                for schema in allowed_schemas_that_exist
                if schema not in schemas_with_existing_privs_set
            ]

            db_team_roles_to_revoke = [
                db_team_role
                for db_team_role in db_team_roles_previously_granted
                if db_team_role not in db_team_roles_set
            ]
            db_team_roles_to_grant = [
                db_team_role
                for db_team_role in db_team_roles
                if db_team_role not in db_team_roles_previously_granted_set
            ]

            # Create user. Note that in PostgreSQL a USER and ROLE are almost the same thing, the
            # difference is that by default a ROLE is "NOLOGIN", so can't be used to connect to
            # the database, i.e. it really is more of a "group".
            cur.execute(
                sql.SQL(
                    "CREATE USER {user} WITH PASSWORD {password} VALID UNTIL {valid_until}"
                ).format(
                    user=sql.Identifier(db_user),
                    password=sql.Literal(db_password),
                    valid_until=sql.Literal(valid_until),
                ),
            )

            # ... create schemas
            for _db_role, _db_schema in list(zip(db_team_roles, db_team_schemas)) + [
                (db_role, db_schema)
            ]:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {};").format(
                        sql.Identifier(_db_schema),
                        sql.Identifier(_db_role),
                    )
                )

            # Give the roles reasonable timeouts...
            # [Out of paranoia on all roles in case the user change role mid session]
            for _db_user in [db_role, db_user] + db_team_roles:
                cur.execute(
                    sql.SQL(
                        "ALTER USER {} SET idle_in_transaction_session_timeout = '60min';"
                    ).format(sql.Identifier(_db_user))
                )
                cur.execute(
                    sql.SQL("ALTER USER {} SET statement_timeout = '60min';").format(
                        sql.Identifier(_db_user)
                    )
                )
                cur.execute(
                    sql.SQL("ALTER USER {} SET pgaudit.log = {};").format(
                        sql.Identifier(_db_user),
                        sql.Literal(settings.PGAUDIT_LOG_SCOPES),
                    )
                )
                cur.execute(
                    sql.SQL("ALTER USER {} SET pgaudit.log_catalog = off;").format(
                        sql.Identifier(_db_user),
                        sql.Literal(settings.PGAUDIT_LOG_SCOPES),
                    )
                )
                cur.execute(
                    sql.SQL("ALTER USER {} WITH CONNECTION LIMIT 10;").format(
                        sql.Identifier(_db_user),
                    )
                )

        # PostgreSQL doesn't handle concurrent GRANT/REVOKEs on the same objects well, so we lock
        with cache.lock(
            "database-grant-v1",
            blocking_timeout=15,
            timeout=180,
        ), connections[database_obj.memorable_name].cursor() as cur:
            logger.info(
                "Revoking permissions ON %s %s from %s",
                database_obj.memorable_name,
                schemas_to_revoke,
                db_role,
            )
            if schemas_to_revoke:
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {};").format(
                        sql.SQL(",").join(sql.Identifier(schema) for schema in schemas_to_revoke),
                        sql.Identifier(db_role),
                    )
                )

            logger.info(
                "Revoking permissions ON %s %s from %s",
                database_obj.memorable_name,
                tables_to_revoke,
                db_role,
            )
            if tables_to_revoke:
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON {} FROM {};").format(
                        sql.SQL(",").join(
                            [sql.Identifier(schema, table) for schema, table in tables_to_revoke]
                        ),
                        sql.Identifier(db_role),
                    )
                )

            logger.info(
                "Granting permissions ON %s %s from %s",
                database_obj.memorable_name,
                schemas_to_grant,
                db_role,
            )
            if schemas_to_grant:
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {};").format(
                        sql.SQL(",").join([sql.Identifier(schema) for schema in schemas_to_grant]),
                        sql.Identifier(db_role),
                    )
                )
            logger.info(
                "Granting SELECT ON %s %s from %s",
                database_obj.memorable_name,
                tables_to_grant,
                db_role,
            )
            if tables_to_grant:
                cur.execute(
                    sql.SQL("GRANT SELECT ON {} TO {};").format(
                        sql.SQL(",").join(
                            [sql.Identifier(schema, table) for schema, table in tables_to_grant]
                        ),
                        sql.Identifier(db_role),
                    )
                )

            logger.info(
                "Revoking %s from %s",
                db_team_roles_to_revoke,
                db_role,
            )
            if db_team_roles_to_revoke:
                cur.execute(
                    sql.SQL("REVOKE {} FROM {};").format(
                        sql.SQL(",").join(
                            [
                                sql.Identifier(db_team_role)
                                for db_team_role in db_team_roles_to_revoke
                            ]
                        ),
                        sql.Identifier(db_role),
                    )
                )
                for team_role in db_team_roles_to_revoke:
                    cur.execute(
                        sql.SQL(
                            """
                            ALTER DEFAULT PRIVILEGES
                            FOR USER {}
                            IN SCHEMA {}
                            REVOKE ALL ON TABLES FROM {};
                            """
                        ).format(
                            sql.Identifier(db_role),
                            sql.Identifier(team_role),
                            sql.Identifier(team_role),
                        )
                    )

            logger.info(
                "Granting %s to %s",
                db_team_roles_to_grant,
                db_role,
            )
            if db_team_roles_to_grant:
                cur.execute(
                    sql.SQL("GRANT {} TO {};").format(
                        sql.SQL(",").join(
                            [
                                sql.Identifier(db_team_role)
                                for db_team_role in db_team_roles_to_grant
                            ]
                        ),
                        sql.Identifier(db_role),
                    )
                )
                # When this user creates a table in a team schema
                # ensure all members of that team can access it
                for team_role in db_team_roles_to_grant:
                    cur.execute(
                        sql.SQL(
                            """
                            ALTER DEFAULT PRIVILEGES
                            FOR USER {}
                            IN SCHEMA {}
                            GRANT ALL ON TABLES TO {};
                            """
                        ).format(
                            sql.Identifier(db_role),
                            sql.Identifier(team_role),
                            sql.Identifier(team_role),
                        )
                    )

            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {};").format(
                    sql.Identifier(database_data["NAME"]), sql.Identifier(db_role)
                )
            )
            cur.execute(
                sql.SQL("GRANT {} TO {};").format(sql.Identifier(db_role), sql.Identifier(db_user))
            )

        # Make it so by default, objects created by the user are owned by the role
        with connections[database_obj.memorable_name].cursor() as cur:
            cur.execute(
                sql.SQL("ALTER USER {} SET ROLE {};").format(
                    sql.Identifier(db_user), sql.Identifier(db_role)
                )
            )

        return {
            "memorable_name": database_obj.memorable_name,
            "db_id": database_obj.id,
            "db_name": database_data["NAME"],
            "db_host": database_data["HOST"],
            "db_port": database_data["PORT"],
            "db_user": db_user,
            "db_persistent_role": db_role,
            "db_password": db_password,
        }

    database_to_tables = {
        database_obj: [
            (source_table["schema"], source_table["table"])
            for source_table in source_tables_for_database
        ]
        for database_obj, source_tables_for_database in itertools.groupby(
            source_tables, lambda source_table: source_table["database"]
        )
    }

    # Sometime we want to make sure credentials have been created for a database, even if the user has no explicit
    # access to tables in that database (e.g. for Data Explorer, where ensuring they can always connect to the database
    # can prevent a number of failure conditions.)
    for extra_db in force_create_for_databases:
        if extra_db not in database_to_tables:
            database_to_tables[extra_db] = []

    creds = [
        get_new_credentials(database_obj, tables)
        for database_obj, tables in database_to_tables.items()
    ]

    if dw_user is not None:
        DatabaseUser.objects.create(owner=dw_user, username=db_user)

    return creds


def write_credentials_to_bucket(user, creds):
    logger.info("settings.NOTEBOOKS_BUCKET %s", settings.NOTEBOOKS_BUCKET)
    if settings.NOTEBOOKS_BUCKET is not None:
        bucket = settings.NOTEBOOKS_BUCKET
        s3_client = get_s3_client()
        s3_prefix = (
            "user/federated/"
            + stable_identification_suffix(str(user.profile.sso_id), short=False)
            + "/"
        )

        logger.info("Saving creds for %s to %s %s", user, bucket, s3_prefix)
        for cred in creds:
            key = f'{s3_prefix}.credentials/db_credentials_{cred["db_name"]}'
            object_contents = (
                f'dbuser {cred["db_user"]}\n'
                f'dbpass {cred["db_password"]}\n'
                f'dbname {cred["db_name"]}\n'
                f'dbhost {cred["db_host"]}\n'
                f'dbport {cred["db_port"]}\n'
                f'dbmemorablename {cred["memorable_name"]}\n'
            )
            s3_client.put_object(
                Body=object_contents.encode("utf-8"),
                Bucket=bucket,
                Key=key,
                ACL="bucket-owner-full-control",
            )


def can_access_schema_table(user, database, schema, table):
    sourcetable = SourceTable.objects.filter(
        schema=schema, table=table, database__memorable_name=database
    )
    has_source_table_perms = (
        DataSet.objects.live()
        .filter(
            Q(published=True)
            & Q(sourcetable__in=sourcetable)
            & (
                Q(
                    user_access_type__in=[
                        UserAccessType.REQUIRES_AUTHENTICATION,
                        UserAccessType.OPEN,
                    ]
                )
                | Q(datasetuserpermission__user=user)
            )
        )
        .exists()
    )

    return has_source_table_perms


def get_team_schemas_for_user(user):
    teams = Team.objects.filter(member=user)
    teams = [{"name": team.name, "schema_name": team.schema_name} for team in teams]

    return teams


def get_all_schemas():
    db_name = list(settings.DATABASES_DATA.items())[0][0]
    with connections[db_name].cursor() as cursor:
        cursor.execute(
            SQL(
                """
                SELECT
                    schema_name
                FROM
                    information_schema.schemata
                WHERE
                    schema_name NOT IN ('dataflow', 'information_schema', 'pg_catalog', 'pg_toast')
                    AND schema_name NOT LIKE 'pg_temp_%'
                    AND schema_name NOT LIKE 'pg_toast_temp_%'
                    AND schema_name NOT LIKE '_user_%'
                    AND schema_name NOT LIKE '_team_%'
                ORDER BY
                    1 ASC
                """
            )
        )
        schemas = [c[0] for c in cursor.fetchall()]
    return schemas


def create_new_schema(schema_name):
    db_name = list(settings.DATABASES_DATA.items())[0][0]
    with connections[db_name].cursor() as cursor:
        cursor.execute(
            SQL(
                """
                CREATE SCHEMA {}
                """
            ).format(sql.Identifier(schema_name))
        )


def source_tables_for_user(user):
    user_email_domain = user.email.split("@")[1]

    req_authentication_tables = SourceTable.objects.filter(
        Q(
            dataset__user_access_type__in=[
                UserAccessType.REQUIRES_AUTHENTICATION,
                UserAccessType.OPEN,
            ]
        ),
        dataset__deleted=False,
        **{"dataset__published": True} if not user.is_superuser else {},
    )
    req_authorization_tables = SourceTable.objects.filter(
        dataset__user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        dataset__deleted=False,
        dataset__datasetuserpermission__user=user,
        **{"dataset__published": True} if not user.is_superuser else {},
    )
    automatically_authorized_tables = SourceTable.objects.filter(
        dataset__deleted=False,
        dataset__authorized_email_domains__contains=[user_email_domain],
        **{"dataset__published": True} if not user.is_superuser else {},
    )
    source_tables = [
        {
            "database": x.database,
            "schema": x.schema,
            "table": x.table,
            "dataset": {
                "id": x.dataset.id,
                "name": x.dataset.name,
                "user_access_type": x.dataset.user_access_type,
            },
        }
        for x in req_authentication_tables.union(
            req_authorization_tables, automatically_authorized_tables
        )
    ]
    reference_dataset_tables = [
        {
            "database": x.external_database,
            "schema": "public",
            "table": x.table_name,
            "dataset": {
                "id": x.uuid,
                "name": x.name,
                "user_access_type": UserAccessType.REQUIRES_AUTHENTICATION,
            },
        }
        for x in ReferenceDataset.objects.live()
        .filter(deleted=False, **{"published": True} if not user.is_superuser else {})
        .exclude(external_database=None)
    ]
    return source_tables + reference_dataset_tables


def source_tables_for_app(application_template):
    req_authentication_tables = SourceTable.objects.filter(
        Q(
            dataset__user_access_type__in=[
                UserAccessType.REQUIRES_AUTHENTICATION,
                UserAccessType.OPEN,
            ]
        ),
        dataset__published=True,
        dataset__deleted=False,
    )
    req_authorization_tables = SourceTable.objects.filter(
        dataset__published=True,
        dataset__deleted=False,
        dataset__user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        dataset__datasetapplicationtemplatepermission__application_template=application_template,
    )
    source_tables = [
        {
            "database": x.database,
            "schema": x.schema,
            "table": x.table,
            "dataset": {
                "id": x.dataset.id,
                "name": x.dataset.name,
                "user_access_type": x.dataset.user_access_type,
            },
        }
        for x in req_authentication_tables.union(req_authorization_tables)
    ]
    reference_dataset_tables = [
        {
            "database": x.external_database,
            "schema": "public",
            "table": x.table_name,
            "dataset": {
                "id": x.uuid,
                "name": x.name,
                "user_access_type": UserAccessType.REQUIRES_AUTHENTICATION,
            },
        }
        for x in ReferenceDataset.objects.live()
        .filter(published=True, deleted=False)
        .exclude(external_database=None)
    ]
    return source_tables + reference_dataset_tables


def view_exists(database, schema, view):
    with connect(database_dsn(settings.DATABASES_DATA[database])) as conn, conn.cursor() as cur:
        return _view_exists(cur, schema, view)


def _view_exists(cur, schema, view):
    cur.execute(
        """
        SELECT 1
        FROM pg_catalog.pg_views
        WHERE schemaname = %(schema)s
        AND viewname = %(view)s
        UNION
        SELECT 1
        FROM pg_catalog.pg_matviews
        WHERE schemaname = %(schema)s
        AND matviewname = %(view)s
    """,
        {"schema": schema, "view": view},
    )
    return bool(cur.fetchone())


def table_exists(database, schema, table):
    with connect(database_dsn(settings.DATABASES_DATA[database])) as conn, conn.cursor() as cur:
        return _table_exists(cur, schema, table)


def _table_exists(cur, schema, table):
    cur.execute(
        """
        SELECT 1
        FROM
            pg_tables
        WHERE
            schemaname = %s
        AND
            tablename = %s
    """,
        (schema, table),
    )
    return bool(cur.fetchone())


def tables_and_views_that_exist(cur, schema_tables):
    if not schema_tables:
        return []
    cur.execute(
        sql.SQL(
            """
        SELECT
            schemaname AS schema, tablename AS name
        FROM
            pg_catalog.pg_tables
        WHERE (
            (schemaname, tablename) IN ({existing})
        )
        UNION
        SELECT
            schemaname AS schema, viewname AS name
        FROM
            pg_catalog.pg_views
        WHERE
            (schemaname, viewname) IN ({existing})
        UNION
        SELECT
            schemaname AS schema, matviewname AS name
        FROM
            pg_catalog.pg_matviews
        WHERE
             (schemaname, matviewname) IN ({existing})
    """
        ).format(
            existing=sql.SQL(",").join(
                [
                    (
                        sql.SQL("(")
                        + sql.Literal(schema)
                        + sql.SQL(",")
                        + sql.Literal(table)
                        + sql.SQL(")")
                    )
                    for (schema, table) in schema_tables
                ]
            )
        )
    )

    return cur.fetchall()


def streaming_query_response(
    user_email: str,
    database: str,
    query,
    filename,
    query_params=None,
    unfiltered_query=None,
    query_metrics_callback=None,
    cursor_name="data_download",
):
    """
    Returns a streaming http response containing a csv file for download

    when provided will callback with query metrics details
    * Total number of rows in original query vs number of rows requested
    * Total number of columns in origin vs number of columns requested

    @param user_email: for logging - who initiated this download
    @param database: name of database where the query should be executed
    @param query: psycopg2 composed SQL query
    @param filename: the filename that should be generated
    @param query_params: additional query parameters applied to query
    @param unfiltered_query: the query without any filters applied
    @param query_metrics_callback: function to call with query metrics data
    @param cursor_name: optional name for the cursor - helps with debugging locks
    @return: Customised DjangoStreamingResponse
    """
    logger.info("streaming_query_response start: %s %s %s", user_email, database, query)

    if unfiltered_query and not query_metrics_callback:
        logger.warning("Missing value for query_metrics_callback.")

    logger.debug("query_params %s", query_params)

    batch_size = 1000
    query_timeout = 300 * 1000
    idle_in_transaction_timeout = 60 * 1000

    # done is added to the queue once the download of the data for the browser is complete
    # this causes the generator to finish and processing to continue
    done = object()

    # if an exception occurs within the greenlet we need to signal this to the generator
    # so we create an instance of ExceptionRaisedInGreenlet and add to the queue
    # the generator checks for this and will re-raise the exception to the view
    class ExceptionRaisedInGreenlet:
        def __init__(self):
            self.exception = None

    exception_raised = ExceptionRaisedInGreenlet()

    # maxsize of 1 means memory use will be 1 * batch_size * bytes per row
    q = gevent.queue.Queue(maxsize=1)

    def stream_query_as_csv_to_queue(conn):
        class PseudoBuffer:
            def write(self, value):
                return value

        pseudo_buffer = PseudoBuffer()
        csv_writer = csv.writer(pseudo_buffer, quoting=csv.QUOTE_NONNUMERIC)

        filtered_columns = []
        start = timer()

        with conn.cursor(name=cursor_name) as cur:

            cur.itersize = batch_size
            cur.arraysize = batch_size
            cur.execute(query, query_params)

            i = 0
            total_bytes = 0
            while True:
                rows = cur.fetchmany(batch_size)

                if i == 0:
                    # Column names are not populated until the first row fetched
                    filtered_columns = [column_desc[0] for column_desc in cur.description]
                    # don't block this q.put call as it is the first thing to be pushed
                    q.put(csv_writer.writerow(filtered_columns))

                if not rows:
                    break

                bytes_fetched = "".join(csv_writer.writerow(row) for row in rows).encode("utf-8")

                i += len(rows)
                total_bytes += len(bytes_fetched)

                logger.debug("fetched %s rows", len(rows))
                logger.debug("total bytes %s", total_bytes)
                q.put(bytes_fetched, block=True, timeout=query_timeout)

            q.put(csv_writer.writerow(["Number of rows: " + str(i)]))

        q.put(done)
        end = timer()

        return filtered_columns, i, total_bytes, end - start

    def get_all_columns_from_unfiltered(conn):
        logger.debug("get_all_columns_from_unfiltered")
        columns_query = sql.SQL("SELECT * FROM ({query}) as data LIMIT 1").format(
            query=unfiltered_query
        )
        with conn.cursor() as cur:
            cur.execute(columns_query)
            columns = [column_desc[0] for column_desc in cur.description]

        return columns

    def get_row_count_from_unfiltered(conn):
        logger.debug("get_row_count_from_unfiltered")
        total_query = sql.SQL("SELECT COUNT(*) from ({query}) as data;").format(
            query=unfiltered_query,
        )

        with conn.cursor() as cur:
            cur.execute(total_query)
            counts = cur.fetchone()

        return counts[0]

    def run_queries():
        should_run_query_metrics = unfiltered_query and query_metrics_callback

        with connect(
            database_dsn(settings.DATABASES_DATA[database]),
            options=(
                f"-c idle_in_transaction_session_timeout={idle_in_transaction_timeout} "
                f"-c statement_timeout={query_timeout}"
            ),
        ) as conn:
            conn.set_session(readonly=True)

            with conn.cursor() as _cur:
                # set statements can't be issued in the server-side cursor,
                # used by stream_query_as_csv_to_queue so we create a separate
                # one to set a timeout on the current connection
                _cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

            (
                filtered_columns,
                filtered_rows_count,
                total_bytes,
                seconds_elapsed,
            ) = stream_query_as_csv_to_queue(conn)

            if should_run_query_metrics:
                # we run this using the connection context and only return the data to caller
                # once the context / connection is closed to avoid djangodb and datatdb connections
                # being open at the same time
                all_columns = get_all_columns_from_unfiltered(conn)
                all_rows_count = get_row_count_from_unfiltered(conn)

        if should_run_query_metrics:
            metrics = {
                "bytes_downloaded": total_bytes,
                "column_count": len(all_columns),
                "column_count_filtered": len(filtered_columns),
                "download_time_in_seconds": seconds_elapsed,
                "row_count": all_rows_count,
                "row_count_filtered": filtered_rows_count,
            }

            query_metrics_callback(metrics)

    def csv_iterator():
        # Listen for all data on the queue until we receive the done object
        # this means that the filtered part of the query is complete
        # and we can return
        while True:
            data = q.get(block=True, timeout=query_timeout)

            if data is done:
                break

            if data is exception_raised:
                logger.debug("exception was raised elsewhere. Terminating download")
                raise exception_raised.exception

            if data:
                yield data

    def exception_callback(g):
        try:
            g.get()
        except Exception as e:
            logger.error(e, exc_info=True)
            # this is picked up in csv_iterator if it is still running
            # which willl stop the download
            exception_raised.exception = e
            q.put(exception_raised)
            raise

    g = gevent.spawn(run_queries)
    g.link_exception(exception_callback)

    response = StreamingHttpResponseWithoutDjangoDbConnection(
        csv_iterator(),
        content_type="text/csv",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    logger.info("streaming_query_response end: %s %s %s", user_email, database, query)

    return response


def get_random_data_sample(database, query, sample_size):
    query_timeout = 300 * 1000
    batch_size = sample_size * 100  # batch size to take sample from
    minimize_nulls_sample_size = sample_size * 2  # sample size before minimizing nulls

    with connect(database_dsn(settings.DATABASES_DATA[database])) as conn, conn.cursor(
        name="data_preview"
    ) as cur:  # Named cursor => server-side cursor

        conn.set_session(readonly=True)

        # set statements can't be issued in a server-side cursor, so we
        # need to create a separate one to set a timeout on the current
        # connection
        with conn.cursor() as _cur:
            _cur.execute("SET statement_timeout={0}".format(query_timeout))

            try:
                cur.execute(query)
            except psycopg2.Error:
                logger.error("Failed to get sample data", exc_info=True)
                return []

        rows = cur.fetchmany(batch_size)
        sample = random.sample(rows, min(minimize_nulls_sample_size, len(rows)))
        sample.sort(key=lambda row: sum(value is not None for value in row), reverse=True)
        sample = sample[:sample_size]
        random.shuffle(sample)

        return sample


def table_data(user_email, database, schema, table, filename=None):
    # There is no ordering here. We just want a full dump.
    # Also, there are not likely to be updates, so a long-running
    # query shouldn't cause problems with concurrency/locking
    query = sql.SQL("SELECT * FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    if filename is None:
        filename = f"{schema}_{table}.csv"
    return streaming_query_response(user_email, database, query, filename)


def get_s3_prefix(user_sso_id):
    return "user/federated/" + stable_identification_suffix(user_sso_id, short=False) + "/"


def create_tools_access_iam_role(user_email_address, user_sso_id, access_point_id):
    s3_prefix = get_s3_prefix(user_sso_id)

    user = get_user_model().objects.get(email=user_email_address)
    if user.profile.tools_access_role_arn:
        return user.profile.tools_access_role_arn, s3_prefix

    iam_client = get_iam_client()

    assume_role_policy_document = settings.S3_ASSUME_ROLE_POLICY_DOCUMENT
    policy_name = settings.S3_POLICY_NAME
    policy_document_template = settings.S3_POLICY_DOCUMENT_TEMPLATE
    permissions_boundary_arn = settings.S3_PERMISSIONS_BOUNDARY_ARN
    role_prefix = settings.S3_ROLE_PREFIX

    role_name = role_prefix + user_email_address
    max_attempts = 10

    try:
        iam_client.create_role(
            RoleName=role_name,
            Path="/",
            AssumeRolePolicyDocument=assume_role_policy_document,
            PermissionsBoundary=permissions_boundary_arn,
        )
    except iam_client.exceptions.EntityAlreadyExistsException:
        # If the role already exists, we might need to update its assume role
        # policy document
        for i in range(0, max_attempts):
            try:
                iam_client.update_assume_role_policy(
                    RoleName=role_name, PolicyDocument=assume_role_policy_document
                )
            except iam_client.exceptions.NoSuchEntityException:
                if i == max_attempts - 1:
                    raise
                gevent.sleep(1)
            else:
                break

    for i in range(0, max_attempts):
        try:
            role_arn = iam_client.get_role(RoleName=role_name)["Role"]["Arn"]
            logger.info("User (%s) set up AWS role... done (%s)", user_email_address, role_arn)
        except iam_client.exceptions.NoSuchEntityException:
            if i == max_attempts - 1:
                raise
            gevent.sleep(1)
        else:
            break

    for i in range(0, max_attempts):
        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=policy_document_template.replace(
                    "__S3_PREFIX__", s3_prefix
                ).replace("__ACCESS_POINT_ID__", access_point_id or ""),
            )
        except iam_client.exceptions.NoSuchEntityException:
            if i == max_attempts - 1:
                raise
            gevent.sleep(1)
        else:
            break

    # Cache the role_arn so it can be retrieved in the future without calling AWS
    user.profile.tools_access_role_arn = role_arn
    user.save()

    return role_arn, s3_prefix


def without_duplicates_preserve_order(seq):
    # https://stackoverflow.com/a/480227/1319998
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


class StreamingHttpResponseWithoutDjangoDbConnection(StreamingHttpResponse):
    # Causes Django to "close" the database connection of the default database
    # on start rather than the end of the response. It's "close", since from
    # Django's point of view its closed, but we we currently use
    # django-db-geventpool which overrides "close" to replace the connection
    # into a pool to be reused later
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        close_admin_db_connection_if_not_in_atomic_block()


def stable_identification_suffix(identifier, short):
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    if short:
        return digest[:8]
    return digest


def close_all_connections_if_not_in_atomic_block(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        finally:
            for conn in connections.all():
                if not conn.in_atomic_block:
                    conn.close()

    return wrapper


def close_admin_db_connection_if_not_in_atomic_block():
    # Note, in unit tests the pytest.mark.django_db decorator wraps each test
    # in a transaction that's rolled back at the end of the test. The check
    # against in_atomic_block is to get those tests to pass. This is
    # unfortunate, since they then don't test what happens in production when
    # the connection is closed. However some of the integration tests, which
    # run in a separate process, do test this behaviour. We could mock
    # close_old_connections in each of those unit tests, but we'll get the
    # same problem. Opting to change the production code to handle this case,
    # since it's probably the right thing to not close the connection if in
    # the middle of a transaction.
    if not connection.in_atomic_block:
        connection.close()


def clean_db_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[-1])[0]
    identifier = re.sub(r"[^\w\s-]", "", identifier).strip().lower()
    return re.sub(r"[-\s]+", "_", identifier)


def get_s3_csv_column_types(path):
    client = get_s3_client()

    # Let's just read the first 100KiB of the file and assume that will give us enough lines to make reasonable
    # assumptions about data types. This is an alternative to reading the first ~10 lines, in which case the first line
    # could be incredibly long and possibly even crash the server?
    # Django's default permitted size for a request body is 2.5MiB, so reading 100KiB here doesn't feel like an
    # additional vector for denial-of-service.
    file = client.get_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path, Range="bytes=0-102400")

    fh = StringIO(file["Body"].read().decode("utf-8-sig"))
    rows = list(csv.reader(fh))

    if len(rows) <= 2:
        raise ValueError("Unable to read enough lines of data from file", path)

    # Drop the last line, which might be incomplete
    del rows[-1]

    # Pare down to a max of 10 lines so that inferring datatypes is quicker
    del rows[10:]

    schema = Schema()
    schema.infer(rows, confidence=1, headers=1)

    fields = []
    for idx, field in enumerate(schema.descriptor["fields"]):
        fields.append(
            {
                "header_name": field["name"],
                "column_name": clean_db_identifier(field["name"]),
                "data_type": SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                    TABLESCHEMA_FIELD_TYPE_MAP.get(field["type"], field["type"]),
                    PostgresDataTypes.TEXT,
                ),
                "sample_data": [row[idx] for row in rows][:6],
            }
        )
    return fields


def trigger_dataflow_dag(conf, dag, dag_run_id):
    config = settings.DATAFLOW_API_CONFIG
    trigger_url = f'{config["DATAFLOW_BASE_URL"]}/api/experimental/' f"dags/{dag}/dag_runs"
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    method = "POST"
    content_type = "application/json"
    body = json.dumps(
        {
            "run_id": dag_run_id,
            "replace_microseconds": "false",
            "conf": conf,
        }
    )

    header = Sender(
        hawk_creds,
        trigger_url,
        method.lower(),
        content=body,
        content_type=content_type,
    ).request_header

    response = requests.request(
        method,
        trigger_url,
        data=body,
        headers={"Authorization": header, "Content-Type": content_type},
    )
    response.raise_for_status()
    return response.json()


def copy_file_to_uploads_bucket(from_path, to_path):
    client = get_s3_client()
    client.copy_object(
        CopySource={"Bucket": settings.NOTEBOOKS_BUCKET, "Key": from_path},
        Bucket=settings.AWS_UPLOADS_BUCKET,
        Key=to_path,
    )


def get_dataflow_dag_status(dag, execution_date):
    config = settings.DATAFLOW_API_CONFIG
    url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/'
        f'dags/{dag}/dag_runs/{execution_date.split("+")[0]}'
    )
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    header = Sender(
        hawk_creds,
        url,
        "get",
        content="",
        content_type="",
    ).request_header
    response = requests.get(
        url,
        headers={"Authorization": header, "Content-Type": ""},
    )
    response.raise_for_status()
    return response.json()


def get_dataflow_task_status(dag, execution_date, task_id):
    config = settings.DATAFLOW_API_CONFIG
    url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/'
        f"dags/{dag}/dag_runs/"
        f'{execution_date.split("+")[0]}/tasks/{task_id}'
    )
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    header = Sender(hawk_creds, url, "get", content="", content_type="").request_header
    response = requests.get(url, headers={"Authorization": header, "Content-Type": ""})
    response.raise_for_status()
    return response.json().get("state")


def get_dataflow_task_log(dag, execution_date, task_id):
    config = settings.DATAFLOW_API_CONFIG
    url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/derived-dags/'
        f"dag/{dag}/{execution_date.split('+')[0]}/{task_id}/log"
    )
    header = Sender(
        {
            "id": config["DATAFLOW_HAWK_ID"],
            "key": config["DATAFLOW_HAWK_KEY"],
            "algorithm": "sha256",
        },
        url,
        "get",
        content="",
        content_type="",
    ).request_header
    response = requests.get(url, headers={"Authorization": header, "Content-Type": ""})
    response.raise_for_status()
    return response.json().get("log")


def get_task_error_message_template(execution_date, task_name):
    logs = get_dataflow_task_log(
        settings.DATAFLOW_API_CONFIG["DATAFLOW_S3_IMPORT_DAG"],
        unquote(execution_date).replace(" ", "+"),
        task_name,
    )
    for error_re, template_name in DATA_FLOW_TASK_ERROR_MAP.items():
        if re.match(error_re, logs, re.DOTALL | re.IGNORECASE):
            return template_name
    return None
