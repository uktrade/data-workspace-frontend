from base64 import urlsafe_b64encode
import csv
import datetime
import json
from functools import wraps
import hashlib
from io import StringIO
import itertools
import logging
import os
import random
import re
import secrets
import string
import time
from contextlib import contextmanager
from timeit import default_timer as timer
from typing import Tuple
from urllib.parse import unquote

import boto3
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections, connection
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.http import StreamingHttpResponse
import gevent
import gevent.queue
from mohawk import Sender
import psycopg2
from psycopg2 import connect, sql
from psycopg2.sql import SQL
import requests
from tableschema import Schema
import redis

from dataworkspace.apps.core.boto3_client import get_s3_client, get_iam_client
from dataworkspace.apps.core.constants import (
    DATA_FLOW_TASK_ERROR_MAP,
    PostgresDataTypes,
    SCHEMA_POSTGRES_DATA_TYPE_MAP,
    TABLESCHEMA_FIELD_TYPE_MAP,
)
from dataworkspace.apps.core.models import DatabaseUser, Team, TeamMembership
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import (
    DataSet,
    SourceTable,
    ReferenceDataset,
    AdminVisualisationUserPermission,
)
from dataworkspace.apps.eventlog.models import SystemStatLog
from dataworkspace.cel import celery_app

logger = logging.getLogger("app")

USER_SCHEMA_STEM = "_user_"

# A PostgreSQL advisory locking lock ID, used to block concurrent GRANTs to the same database
# objects (other than GRANTing role membership, which we think doesn't need locking)
GLOBAL_LOCK_ID = 1


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


@contextmanager
def get_cursor(database_memorable_name):
    with connections[database_memorable_name].cursor() as cursor:
        cursor.execute(sql.SQL("SET statement_timeout = '30s'"))
        yield cursor


@contextmanager
def transaction_and_lock(cursor, lock_id):
    try:
        cursor.execute(sql.SQL("BEGIN"))
        cursor.execute(
            sql.SQL("SELECT pg_advisory_xact_lock({lock_id})").format(lock_id=sql.Literal(lock_id))
        )
        yield
    except Exception:  # pylint: disable=broad-except
        cursor.execute(sql.SQL("ROLLBACK"))
        raise
    else:
        cursor.execute(sql.SQL("COMMIT"))


def ensure_db_role(cur, db_role_name):
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


def new_private_database_credentials(
    db_role_and_schema_suffix,
    source_tables,
    db_user,
    dw_user: get_user_model(),
    valid_for: datetime.timedelta,
    force_create_for_databases: Tuple[str] = tuple(),
):
    db_shared_roles = (
        []
        if dw_user is None
        else ([team.schema_name for team in Team.objects.filter(member=dw_user)])
    ) + (
        []
        if dw_user is None
        else (
            [
                USER_SCHEMA_STEM
                + db_role_schema_suffix_for_app(permission.visualisation.visualisation_template)
                for permission in AdminVisualisationUserPermission.objects.filter(user=dw_user)
            ]
        )
    )
    db_shared_roles_set = set(db_shared_roles)
    db_shared_schemas = db_shared_roles

    # This function can take a while. That isn't great, but also not great to
    # hold a connection to the admin database
    close_admin_db_connection_if_not_in_atomic_block()

    password_alphabet = string.ascii_letters + string.digits

    def postgres_password():
        return "".join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_memorable_name, tables):
        # Each real-world user is given
        # - a private and permanent schema where they can manage tables and rows as needed
        # - a permanent database role that is the owner of the schema
        # - temporary database users, each of which are GRANTed the role
        start_time = time.time()
        logger.info("Getting new credentials for permanent role %s", db_role_and_schema_suffix)
        db_password = postgres_password()
        db_role = f"{USER_SCHEMA_STEM}{db_role_and_schema_suffix}"
        db_schema = f"{USER_SCHEMA_STEM}{db_role_and_schema_suffix}"

        database_data = settings.DATABASES_DATA[database_memorable_name]
        valid_until = (datetime.datetime.now() + valid_for).isoformat()

        with get_cursor(database_memorable_name) as cur:
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

            for db_role_name in db_shared_roles + [db_role]:
                ensure_db_role(cur, db_role_name)

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
                cur.execute(
                    sql.SQL("GRANT {} TO {};").format(
                        sql.SQL(",").join(
                            sql.Identifier(missing_db_role) for missing_db_role in missing_db_roles
                        ),
                        sql.Identifier(database_data["USER"]),
                    )
                )

        logging.info("Trying to get cached table permissions")
        tables_with_existing_privs_set = set(
            table_permissions_for_role(
                db_role, db_schema, database_memorable_name, log_stats=dw_user is not None
            )
        )
        logger.info(
            "Found %d tables with existing permissions for permanent role %s",
            len(tables_with_existing_privs_set),
            db_role,
        )

        tables_with_existing_role_privs_set = set(
            table_role_permissions_for_role(
                db_role, database_memorable_name, log_stats=dw_user is not None
            )
        )
        logger.info(
            "Found %s role based table permissions for role %s: %s",
            len(tables_with_existing_role_privs_set),
            db_role,
            list(tables_with_existing_role_privs_set),
        )

        with get_cursor(database_memorable_name) as cur:
            # Get a list of all tables in the database
            cur.execute(
                sql.SQL(
                    """
                SELECT trim(both '"' from relnamespace::regnamespace::text) AS table_schema, relname AS table_name
                FROM pg_class WHERE relkind IN ('r', 'm', 'v', 'p');
            """
                )
            )
            existing_db_tables = list(cur.fetchall())
            logger.info(
                "Found %d existing tables in the %s db",
                len(existing_db_tables),
                database_memorable_name,
            )
            # Find existing schema permissions granted directly on user's permanent roles
            # (which is the old way - we don't add these any more)
            cur.execute(
                sql.SQL(
                    """
                SELECT DISTINCT
                    nspname AS name
                FROM
                    pg_namespace, aclexplode(nspacl)
                WHERE
                    nspname != {schema}
                    AND grantee = {role}::regrole
                    AND privilege_type IN ('CREATE', 'USAGE')
                ORDER BY nspname;
            """
                ).format(role=sql.Literal(db_role), schema=sql.Literal(db_schema))
            )
            schemas_with_existing_privs = [row[0] for row in cur.fetchall()]
            logger.info(
                "Found %d existing permissions for permanent role %s: %s",
                len(schemas_with_existing_privs),
                db_role,
                schemas_with_existing_privs,
            )

            # Find existing schema permissions granted via schema role membership
            cur.execute(
                sql.SQL(
                    """
                    SELECT
                        roleid::regrole::text
                    FROM
                        pg_auth_members
                    WHERE
                        roleid::regrole::text LIKE 'schema\\_usage\\_%'
                        AND member = {role}::regrole
                    """
                ).format(role=sql.Literal(db_role))
            )
            schema_roles_granted_to_user_role = [role for (role,) in cur.fetchall()]

            # Existing granted team roles to permanent user role
            cur.execute(
                sql.SQL(
                    """
                SELECT
                    rolname
                FROM
                    pg_roles
                WHERE
                    (
                        rolname LIKE '\\_team\\_%'
                        OR rolname LIKE '\\_user\\_app\\_%'
                    )
                    AND pg_has_role({db_role}, rolname, 'member');
            """
                ).format(db_role=sql.Literal(db_role))
            )
            db_shared_roles_previously_granted = [role for (role,) in cur.fetchall()]
            db_shared_roles_previously_granted_set = set(db_shared_roles_previously_granted)

            tables_to_revoke = [
                (schema, table)
                for (schema, table) in tables_with_existing_privs_set
                if (schema, table) not in allowed_tables_that_exist_set
                and (schema, table) in existing_db_tables
            ]
            logger.info("Got %s tables to revoke for role %s", len(tables_to_revoke), db_role)
            if tables_to_revoke:
                tables_to_revoke_oid_map = tables_to_oid_map(cur, tables_to_revoke)
                logger.info("tables_to_revoke_oid_map: %s", tables_to_revoke_oid_map)

            tables_to_grant = [
                (schema, table)
                for (schema, table) in allowed_tables_that_exist
                if (schema, table) not in tables_with_existing_privs_set
                and (schema, table) in existing_db_tables
            ]
            logger.info("Got %s tables to grant for role %s", len(tables_to_grant), db_role)
            if tables_to_grant:
                tables_to_grant_oid_map = tables_to_oid_map(cur, tables_to_grant)
                logger.info("tables_to_grant_oid_map: %s", tables_to_grant_oid_map)

            # Make sure that that privileges granted directly to the user's role, which was done in
            # previous versions, are removed
            schemas_to_revoke = schemas_with_existing_privs
            logger.info("Got %s schemas to revoke for role %s", len(schemas_to_revoke), db_role)

            db_shared_roles_to_revoke = [
                db_shared_role
                for db_shared_role in db_shared_roles_previously_granted
                if db_shared_role not in db_shared_roles_set
            ]
            db_shared_roles_to_grant = [
                db_shared_role
                for db_shared_role in db_shared_roles
                if db_shared_role not in db_shared_roles_previously_granted_set
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
            for _db_role, _db_schema in list(zip(db_shared_roles, db_shared_schemas)) + [
                (db_role, db_schema)
            ]:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {};").format(
                        sql.Identifier(_db_schema),
                        sql.Identifier(_db_role),
                    )
                )

            # Ensure we have a DB connection role
            cur.execute(
                sql.SQL("SELECT oid FROM pg_database WHERE datname = {} LIMIT 1;").format(
                    sql.Literal(database_data["NAME"])
                )
            )
            db_conn_permission_role = f"database_connect_{cur.fetchone()[0]}"
            logger.info(
                "Database %s connection role is %s", database_data["NAME"], db_conn_permission_role
            )
            ensure_db_role(cur, db_conn_permission_role)

            # Grant the DB connection role to the temporary user
            cur.execute(
                sql.SQL("GRANT {} TO {};").format(
                    sql.Identifier(db_conn_permission_role), sql.Identifier(db_user)
                )
            )

            # Ensure we have roles for all schemas
            if allowed_schemas_that_exist:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT
                            nspname, oid
                        FROM
                            pg_namespace
                        WHERE
                            nspname IN ({schemas})
                        ORDER BY
                            nspname
                    """
                    ).format(
                        schemas=sql.SQL(",").join(
                            sql.Literal(schema) for schema in allowed_schemas_that_exist
                        )
                    )
                )
                schema_oids = cur.fetchall()
            else:
                schema_oids = []
            schema_role_names = [(schema, f"schema_usage_{oid}") for schema, oid in schema_oids]
            for _, role_name in schema_role_names:
                ensure_db_role(cur, role_name)

            # Find the schema roles that don't have USAGE on the schemas
            if schema_oids:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT
                            nspname
                        FROM
                            pg_namespace, aclexplode(nspacl)
                        WHERE
                            nspname IN ({schemas})
                            AND grantee::regrole::text = 'schema_usage_' || oid::text
                            AND privilege_type = 'USAGE'
                        ORDER BY
                            nspname
                    """
                    ).format(
                        schemas=sql.SQL(",").join(sql.Literal(schema) for schema, _ in schema_oids)
                    )
                )
                schemas_with_usage = cur.fetchall()
            else:
                schemas_with_usage = []
            schemas_role_names_without_usage = [
                (schema, role)
                for schema, role in schema_role_names
                if schema not in schemas_with_usage
            ]

            # Revoke/grant any schema roles needed
            schema_roles_granted_to_user_role_set = set(schema_roles_granted_to_user_role)
            schema_role_names_dict = dict(schema_role_names)
            allowed_schema_roles_with_existing_schemas_set = {
                schema_role_names_dict[schema] for schema in allowed_schemas_that_exist_set
            }

            logger.info(
                "Working out schemas to revoke based on existing and allowed schemas %s and corresponding roles %s",
                allowed_schemas_that_exist_set,
                allowed_schema_roles_with_existing_schemas_set,
            )
            schema_roles_to_revoke = [
                role_name
                for role_name in schema_roles_granted_to_user_role
                if role_name not in allowed_schema_roles_with_existing_schemas_set
            ]
            schema_roles_to_grant = [
                role_name
                for schema, role_name in schema_role_names
                if role_name not in schema_roles_granted_to_user_role_set
            ]
            logger.info("Revoking schema roles %s from %s", schema_roles_to_revoke, db_role)
            if schema_roles_to_revoke:
                cur.execute(
                    sql.SQL("REVOKE {} FROM {};").format(
                        sql.SQL(",").join(
                            sql.Identifier(schema_role) for schema_role in schema_roles_to_revoke
                        ),
                        sql.Identifier(db_role),
                    )
                )
            logger.info("Granting schema roles %s to %s", schema_roles_to_grant, db_role)
            if schema_roles_to_grant:
                cur.execute(
                    sql.SQL("GRANT {} TO {};").format(
                        sql.SQL(",").join(
                            sql.Identifier(schema_role) for schema_role in schema_roles_to_grant
                        ),
                        sql.Identifier(db_role),
                    )
                )

            # Grant the user's permanent role to the temporary user
            cur.execute(
                sql.SQL("GRANT {} TO {};").format(sql.Identifier(db_role), sql.Identifier(db_user))
            )

            # Check if the database connection role has the right privileges
            cur.execute(
                sql.SQL(
                    """
                    SELECT EXISTS(
                        SELECT
                            1
                        FROM
                            pg_database, aclexplode(datacl)
                        WHERE
                            datname = {}
                            AND grantee = {}::regrole
                            AND privilege_type = 'CONNECT'
                    );
                """
                ).format(sql.Literal(database_data["NAME"]), sql.Literal(db_conn_permission_role))
            )
            db_conn_permission_role_can_connect = cur.fetchone()[0]

            # Check if the user's permanent role has direct connect privs on the database
            # (It shouldn't any more since we moved to getting the CONNECT priv via a role)
            cur.execute(
                sql.SQL(
                    """
                    SELECT EXISTS(
                        SELECT
                            1
                        FROM
                            pg_database, aclexplode(datacl)
                        WHERE
                            datname = {}
                            AND grantee = {}::regrole
                            AND privilege_type = 'CONNECT'
                    );
                """
                ).format(sql.Literal(database_data["NAME"]), sql.Literal(db_role))
            )
            db_role_can_connect = cur.fetchone()[0]

        # PostgreSQL doesn't handle concurrent
        # - GRANT/REVOKEs on the same database object
        # - ALTER USER ... SET
        # Either can result in "tuple concurrentl updated" errors. So we lock.
        with get_cursor(database_memorable_name) as cur, transaction_and_lock(cur, GLOBAL_LOCK_ID):
            for schema, schema_role_name in schemas_role_names_without_usage:
                logger.info("Granting USAGE on %s to role %s", schema, schema_role_name)
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {};").format(
                        sql.Identifier(schema),
                        sql.Identifier(schema_role_name),
                    )
                )

            if not db_conn_permission_role_can_connect:
                logger.info("Granting CONNECT to the role %s", db_conn_permission_role)
                cur.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {};").format(
                        sql.Identifier(database_data["NAME"]),
                        sql.Identifier(db_conn_permission_role),
                    )
                )

            if db_role_can_connect:
                logger.info("Revoking CONNECT to from role %s", db_role)
                cur.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {};").format(
                        sql.Identifier(database_data["NAME"]),
                        sql.Identifier(db_role),
                    )
                )

            # Give the roles reasonable timeouts...
            # [Out of paranoia on all roles in case the user change role mid session]
            for _db_user in [db_role, db_user] + db_shared_roles:
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

            logger.info(
                "Revoking permissions ON %s %s from %s",
                database_memorable_name,
                schemas_to_revoke,
                db_role,
            )
            if schemas_to_revoke:
                # Ensure any directly granted schema perms are still removed while we
                # migrate to role based perms
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {};").format(
                        sql.SQL(",").join(sql.Identifier(schema) for schema in schemas_to_revoke),
                        sql.Identifier(db_role),
                    )
                )

            logger.info(
                "Revoking permissions ON %s %s from %s",
                database_memorable_name,
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
                "Granting SELECT ON %s %s from %s",
                database_memorable_name,
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
                db_shared_roles_to_revoke,
                db_role,
            )
            if db_shared_roles_to_revoke:
                cur.execute(
                    sql.SQL("REVOKE {} FROM {};").format(
                        sql.SQL(",").join(
                            [
                                sql.Identifier(db_shared_role)
                                for db_shared_role in db_shared_roles_to_revoke
                            ]
                        ),
                        sql.Identifier(db_role),
                    )
                )
                for db_shared_role in db_shared_roles_to_revoke:
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
                            sql.Identifier(db_shared_role),
                            sql.Identifier(db_shared_role),
                        )
                    )

            logger.info(
                "Granting %s to %s",
                db_shared_roles_to_grant,
                db_role,
            )
            if db_shared_roles_to_grant:
                cur.execute(
                    sql.SQL("GRANT {} TO {};").format(
                        sql.SQL(",").join(
                            [
                                sql.Identifier(db_shared_role)
                                for db_shared_role in db_shared_roles_to_grant
                            ]
                        ),
                        sql.Identifier(db_role),
                    )
                )
                # When this user creates a table in a team schema
                # ensure all members of that team can access it
                for db_shared_role in db_shared_roles_to_grant:
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
                            sql.Identifier(db_shared_role),
                            sql.Identifier(db_shared_role),
                        )
                    )

        # Make it so by default, objects created by the user are owned by the role
        with get_cursor(database_memorable_name) as cur:
            cur.execute(
                sql.SQL("ALTER USER {} SET ROLE {};").format(
                    sql.Identifier(db_user), sql.Identifier(db_role)
                )
            )

        logger.info(
            "Generated new credentials for permanent role %s in %s seconds",
            db_role,
            round(time.time() - start_time, 2),
        )
        return {
            "memorable_name": database_memorable_name,
            "db_name": database_data["NAME"],
            "db_host": database_data["HOST"],
            "db_port": database_data["PORT"],
            "db_user": db_user,
            "db_persistent_role": db_role,
            "db_password": db_password,
        }

    database_to_tables = {
        database_memorable_name: [
            (source_table["schema"], source_table["table"])
            for source_table in source_tables_for_database
        ]
        for database_memorable_name, source_tables_for_database in itertools.groupby(
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
        get_new_credentials(database_memorable_name, tables)
        for database_memorable_name, tables in database_to_tables.items()
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
        schema=schema, table=table, database__memorable_name=database, published=True
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
    teams = Team.objects.filter(member=user).order_by("schema_name")
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

    # select_related to reduce number of database queries
    # The `dataset__reference_code` field is not used in many cases, but is accessed
    # in the DataSet's __init__ function, and so results in a database query for
    # each Dataset if it isn't select_related or prefetch_related up-front
    req_authentication_tables = SourceTable.objects.filter(
        Q(
            dataset__user_access_type__in=[
                UserAccessType.REQUIRES_AUTHENTICATION,
                UserAccessType.OPEN,
            ]
        ),
        dataset__deleted=False,
        published=True,
        **{"dataset__published": True} if not user.is_superuser else {},
    ).values(
        "database__memorable_name",
        "schema",
        "table",
        "dataset__id",
        "dataset__name",
        "dataset__user_access_type",
    )
    req_authorization_tables = SourceTable.objects.filter(
        dataset__user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        dataset__deleted=False,
        dataset__datasetuserpermission__user=user,
        published=True,
        **{"dataset__published": True} if not user.is_superuser else {},
    ).values(
        "database__memorable_name",
        "schema",
        "table",
        "dataset__id",
        "dataset__name",
        "dataset__user_access_type",
    )
    automatically_authorized_tables = SourceTable.objects.filter(
        dataset__deleted=False,
        dataset__authorized_email_domains__contains=[user_email_domain],
        published=True,
        **{"dataset__published": True} if not user.is_superuser else {},
    ).values(
        "database__memorable_name",
        "schema",
        "table",
        "dataset__id",
        "dataset__name",
        "dataset__user_access_type",
    )
    source_tables = [
        {
            "database": x["database__memorable_name"],
            "schema": x["schema"],
            "table": x["table"],
            "dataset": {
                "id": x["dataset__id"],
                "name": x["dataset__name"],
                "user_access_type": x["dataset__user_access_type"],
            },
        }
        for x in req_authentication_tables.union(
            req_authorization_tables, automatically_authorized_tables
        )
    ]
    reference_dataset_tables = [
        {
            "database": x["external_database__memorable_name"],
            "schema": "public",
            "table": x["table_name"],
            "dataset": {
                "id": x["uuid"],
                "name": x["name"],
                "user_access_type": UserAccessType.REQUIRES_AUTHENTICATION,
            },
        }
        for x in ReferenceDataset.objects.live()
        .filter(deleted=False, **{"published": True} if not user.is_superuser else {})
        .exclude(external_database=None)
        .values("external_database__memorable_name", "table_name", "uuid", "name")
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
        published=True,
    )
    req_authorization_tables = SourceTable.objects.filter(
        published=True,
        dataset__published=True,
        dataset__deleted=False,
        dataset__user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        dataset__datasetapplicationtemplatepermission__application_template=application_template,
    )
    source_tables = [
        {
            "database": x.database.memorable_name,
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
            "database": x.external_database.memorable_name,
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


def check_db(database):
    with connect(database_dsn(settings.DATABASES[database])) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        return bool(cur.fetchone)


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
    should_run_query_metrics = unfiltered_query and query_metrics_callback

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
                metrics = {
                    "bytes_downloaded": total_bytes,
                    "column_count": len(all_columns),
                    "column_count_filtered": len(filtered_columns),
                    "download_time_in_seconds": seconds_elapsed,
                    "row_count": all_rows_count,
                    "row_count_filtered": filtered_rows_count,
                }
                q.put(metrics)

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

        if should_run_query_metrics:
            metrics = q.get(block=True, timeout=query_timeout)
            query_metrics_callback(metrics)

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


def create_tools_access_iam_role(user_id, user_email_address, access_point_id):
    user = get_user_model().objects.get(id=user_id)
    s3_prefixes = get_user_s3_prefixes(user)
    if user.profile.tools_access_role_arn:
        return user.profile.tools_access_role_arn, s3_prefixes

    iam_client = get_iam_client()

    assume_role_policy_document = settings.S3_ASSUME_ROLE_POLICY_DOCUMENT
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

    update_user_tool_access_policy(user, access_point_id)

    # Cache the role_arn so it can be retrieved in the future without calling AWS
    user.profile.tools_access_role_arn = role_arn
    user.save()

    return role_arn, s3_prefixes


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


def clean_db_column_name(column_name):
    """
    Replace forward slashes in column names before cleaning for user
    """
    return clean_db_identifier(column_name.replace("/", ""))


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
                "column_name": clean_db_column_name(field["name"]),
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
    trigger_url = f'{config["DATAFLOW_BASE_URL"]}/api/experimental/dags/{dag}/dag_runs'
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
    upload_config = boto3.s3.transfer.TransferConfig(
        multipart_chunksize=1_048_576 * 1024,
        multipart_threshold=1_048_576 * 1024,
    )
    client.copy(
        CopySource={"Bucket": settings.NOTEBOOKS_BUCKET, "Key": from_path},
        Bucket=settings.AWS_UPLOADS_BUCKET,
        Key=to_path,
        Config=upload_config,
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


def b64encode_nopadding(to_encode):
    return urlsafe_b64encode(to_encode).rstrip(b"=")


def generate_jwt_token(authorised_hosts, sub):
    private_key = load_pem_private_key(settings.JWT_PRIVATE_KEY.encode(), password=None)
    header = {
        "typ": "JWT",
        "alg": "EdDSA",
        "crv": "Ed25519",
    }
    payload = {
        "sub": sub,
        "exp": int(time.time() + 60 * 60 * 24),
        "authorised_hosts": authorised_hosts,
    }
    to_sign = (
        b64encode_nopadding(json.dumps(header).encode("utf-8"))
        + b"."
        + b64encode_nopadding(json.dumps(payload).encode("utf-8"))
    )
    signature = b64encode_nopadding(private_key.sign(to_sign))
    jwt = (to_sign + b"." + signature).decode()
    return jwt


def get_user_s3_prefixes(user):
    return {
        "home": get_s3_prefix(str(user.profile.sso_id)),
        **{x["name"]: f'teams/{x["schema_name"]}/' for x in get_team_schemas_for_user(user)},
    }


def get_team_prefixes(user):
    return [
        {
            "name": x["name"],
            "env_var": f"S3_PREFIX_TEAM_{clean_db_identifier(x['name']).upper()}",
            "prefix": f'teams/{x["schema_name"]}/',
        }
        for x in get_team_schemas_for_user(user)
    ]


def update_user_tool_access_policy(user, access_point_id):
    max_attempts = 10
    iam_client = get_iam_client()
    s3_prefixes = get_user_s3_prefixes(user).values()
    prefix_values = '","'.join([f"{x}*" for x in s3_prefixes])
    bucket_arn = settings.S3_NOTEBOOKS_BUCKET_ARN
    bucket_arns = '","'.join([f"{bucket_arn}/{x}*" for x in s3_prefixes])
    policy_document = (
        settings.S3_POLICY_DOCUMENT_TEMPLATE.replace('"__S3_PREFIXES__"', f'["{prefix_values}"]')
        .replace('"__S3_BUCKET_ARNS__"', f'["{bucket_arns}"]')
        .replace("__ACCESS_POINT_ID__", access_point_id or "")
    )
    for i in range(0, max_attempts):
        try:
            iam_client.put_role_policy(
                RoleName=settings.S3_ROLE_PREFIX + user.email,
                PolicyName=settings.S3_POLICY_NAME,
                PolicyDocument=policy_document,
            )
        except iam_client.exceptions.NoSuchEntityException:
            if i == max_attempts - 1:
                raise
            gevent.sleep(1)
        else:
            break


@celery_app.task(autoretry_for=(redis.exceptions.LockError,))
@close_all_connections_if_not_in_atomic_block
def update_tools_access_policy_task(user_id):
    with cache.lock(
        "update_tools_access_policy_task",
        blocking_timeout=0,
        timeout=360,
    ):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(id=user_id)
        except user_model.DoesNotExist:
            logger.exception("User id %d does not exist", user_id)
        else:
            update_user_tool_access_policy(user, user.profile.home_directory_efs_access_point_id)


@receiver(post_save, sender=TeamMembership)
def team_membership_post_save(instance, **kwargs):
    """
    When a team member is added to a team, update their tools access
    to include the team s3 prefix
    """
    if kwargs["created"] and instance.user.profile.tools_access_role_arn:
        update_tools_access_policy_task.delay(instance.user_id)


@receiver(post_delete, sender=TeamMembership)
def team_membership_post_delete(instance, **_):
    """
    When a team member is removed from a team, update their tools access
    to remove the team s3 prefix
    """
    if instance.user.profile.tools_access_role_arn:
        update_tools_access_policy_task.delay(instance.user_id)


def table_permissions_cache_key(db_role):
    return f"_table_permissions_cache_key_v2{db_role}"


def table_permissions_for_role(db_role, db_schema, database_name, log_stats=False):
    """
    Return a (cached) list of tables that the given role has SELECT/UPDATE/DELETE/ETC perms for.
    """
    key = table_permissions_cache_key(db_role)
    tables_with_perms = cache.get(key)
    if tables_with_perms:
        logger.info("table_perms: Returning cached table permissions for role %s", db_role)
        return tables_with_perms

    pg_class_query = """
        SELECT trim(both '"' from relnamespace::regnamespace::text) AS schema, relname AS name
        FROM pg_class, aclexplode(relacl) acl
        WHERE acl.grantee = {role}::regrole::oid
        AND relkind in ('r', 'p')
        AND acl.privilege_type in (
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        )
        AND trim(both '"' from relnamespace::regnamespace::text) NOT SIMILAR TO
            'pg_toast|pg_temp_%|pg_toast_temp_%|_team_%|_user_%'
        AND relname NOT SIMILAR TO
            '_\\d{{8}}t\\d{{6}}|%_swap|%_idx|_tmp%|%_pkey|%_seq|_data_explorer_tmp%|%000000|_tmp_%';
    """
    logger.info("table_perms: Querying and caching table permissions for role %s", db_role)
    start_time = time.time()
    with get_cursor(database_name) as cur:
        cur.execute(sql.SQL(pg_class_query).format(role=sql.Literal(db_role)))
        tables_with_perms = cur.fetchall()
    run_time = round(time.time() - start_time, 2)
    if log_stats:
        SystemStatLog.objects.log_permissions_query_runtime(
            run_time,
            extra={
                "role": db_role,
                "query_type": "pg_class",
                "legacy": False,
            },
        )
    logger.info(
        "table_perms: Querying table permissions for role %s took %s seconds", db_role, run_time
    )
    cache.set(key, tables_with_perms, timeout=datetime.timedelta(days=7).total_seconds())
    return tables_with_perms


def table_role_permissions_for_role(db_role, database_name, log_stats=False):
    """
    Return a (cached) list of tables that the given role has a table role for.
    """
    with get_cursor(database_name) as cur:
        cur.execute(
            sql.SQL(
                """SELECT roleid::regrole::text
            FROM pg_auth_members
            WHERE (roleid::regrole::text LIKE 'table\\_select\\_%')
            AND member = {role}::regrole;"""
            ).format(role=sql.Literal(db_role))
        )
        return cur.fetchall()


def clear_table_permissions_cache_for_user(user):
    db_role = f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(user)}"
    logger.info(
        "table_perms: Deleting cached table permissions for user %s (db role %s)",
        user.email,
        db_role,
    )
    delete_cache_for_db_role(db_role)


def delete_cache_for_db_role(db_role):
    cache.delete(table_permissions_cache_key(db_role))


def get_postgres_datatype_choices():
    return ((name, name.capitalize()) for name, _ in SCHEMA_POSTGRES_DATA_TYPE_MAP.items())


def tables_to_oid_map(cur, tables):
    cur.execute(
        sql.SQL(
            """
        SELECT nspname ||'.'|| relname, pg_class.oid
        FROM pg_class, pg_namespace
        WHERE relnamespace = pg_namespace.oid
        AND (nspname, relname) in ({table_names})
        AND relkind = 'r';
        """
        ).format(
            table_names=sql.SQL(",").join(
                [
                    sql.SQL("(")
                    + sql.Literal(table[0])
                    + sql.SQL(",")
                    + sql.Literal(table[1])
                    + sql.SQL(")")
                    for table in tables
                ]
            )
        )
    )
    return dict(cur.fetchall())
