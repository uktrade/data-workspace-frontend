import datetime
import hashlib
import itertools
import logging
import re
import secrets
import string

import boto3

from django.conf import (
    settings,
)
from django.db import (
    connections,
)
from django.db.models import (
    Q,
)
from psycopg2 import (
    sql,
    connect,
)

from app.models import (
    DataSet,
    Privilage,
    SourceSchema,
)

logger = logging.getLogger('app')


def database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} '
        f'dbname={database_data["NAME"]} user={database_data["USER"]} '
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def table_exists(database, schema, table):
    with \
            connect(database_dsn(settings.DATABASES_DATA[database])) as conn, \
            conn.cursor() as cur:

        cur.execute("""
            SELECT 1
            FROM
                pg_tables
            WHERE
                schemaname = %s
            AND
                tablename = %s
        """, (schema, table))
        return bool(cur.fetchone())


def get_private_privilages(user):
    logger.info('Getting privilages for: %s', user)
    return Privilage.objects.all().filter(
        database__is_public=False,
        user=user,
    ).order_by(
        'database__memorable_name', 'schema', 'id'
    )


def new_private_database_credentials(user):
    password_alphabet = string.ascii_letters + string.digits
    user_alphabet = string.ascii_lowercase + string.digits

    def postgres_user():
        unique_enough = ''.join(secrets.choice(user_alphabet) for i in range(5))
        return 'user_' + re.sub('[^a-z0-9]', '_', user.email.lower()) + '_' + unique_enough

    def postgres_password():
        return ''.join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, schemas):
        user = postgres_user()
        password = postgres_password()

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.date.today() + datetime.timedelta(days=31)).isoformat()
        with connections[database_obj.memorable_name].cursor() as cur:
            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(
                sql.Identifier(user)), [password, valid_until])
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(
                sql.Identifier(database_data['NAME']), sql.Identifier(user)))

            for schema in schemas:
                logger.info(
                    'Granting permissions to %s %s to %s',
                    database_obj.memorable_name, schema, user)
                cur.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(
                    sql.Identifier(schema), sql.Identifier(user)))
                tables_sql = \
                    sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {};').format(sql.Identifier(schema),
                                                                                     sql.Identifier(user))
                cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': user,
            'db_password': password,
        }

    database_to_schemas_from_privilages = {
        database_obj: [
            privilage.schema for privilage in privilages_for_database
        ]
        for database_obj, privilages_for_database in itertools.groupby(get_private_privilages(user), lambda privilage: privilage.database)
    }
    database_to_schemas_from_source_schemas = {
        database_obj: [
            source_schema.schema for source_schema in source_schemas_for_database
        ]
        for database_obj, source_schemas_for_database in itertools.groupby(source_schemas_for_user(user), lambda source_schema: source_schema.database)
    }

    databases = remove_duplicates(list(database_to_schemas_from_privilages.keys()) + list(database_to_schemas_from_source_schemas.keys()))
    database_to_schemas = {
        database:
        (database_to_schemas_from_privilages[database] if database in database_to_schemas_from_privilages else []) +
            (database_to_schemas_from_source_schemas[database] if database in database_to_schemas_from_source_schemas else [])
        for database in databases
    }

    creds = [
        get_new_credentials(database_obj, schemas)
        for database_obj, schemas in database_to_schemas.items()
    ]

    # Create a profile in case it doesn't have one
    logger.info('settings.NOTEBOOKS_BUCKET %s', settings.NOTEBOOKS_BUCKET)
    if settings.NOTEBOOKS_BUCKET is not None:
        user.save()
        bucket = settings.NOTEBOOKS_BUCKET
        s3_client = boto3.client('s3')
        s3_prefix = 'user/federated/' + \
                    hashlib.sha256(str(user.profile.sso_id).encode('utf-8')).hexdigest() + '/'

        logger.info('Saving creds for %s to %s %s', user, bucket, s3_prefix)
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
                Body=object_contents.encode('utf-8'),
                Bucket=bucket,
                Key=key,
                ACL='bucket-owner-full-control',
            )

    return creds


def can_access_schema(user, privilages, database, schema):
    return can_access_source_schema(user, database, schema) or any(
        True
        for privilage in privilages
        if privilage.database.memorable_name == database and privilage.schema == schema
    )


def can_access_source_schema(user, database, schema):
    sourceschema = SourceSchema.objects.filter(
        schema=schema,
        database__memorable_name=database,
    )
    return DataSet.objects.filter(
        Q(sourceschema__in=sourceschema) & (
            Q(user_access_type='REQUIRES_AUTHENTICATION') |
            Q(datasetuserpermission__user=user)
        ),
    ).exists()


def source_schemas_for_user(user):
    return SourceSchema.objects.filter(
        Q(dataset__user_access_type='REQUIRES_AUTHENTICATION') |
        Q(dataset__datasetuserpermission__user=user)
    ).order_by('database__memorable_name', 'schema', 'id')


def set_application_stopped(application_instance):
    application_instance.state = 'STOPPED'
    application_instance.single_running_or_spawning_integrity = str(application_instance.id)
    application_instance.save()


def tables_in_schema(cur, schema):
    logger.info('tables_in_schema: %s', schema)
    cur.execute("""
        SELECT
            tablename
        FROM
            pg_tables
        WHERE
            schemaname = %s
    """, (schema,))
    results = [result[0] for result in cur.fetchall()]
    logger.info('tables_in_schema: %s %s', schema, results)
    return results


def remove_duplicates(to_have_duplicates_removed):
    seen = set()
    seen_add = seen.add
    return [x for x in to_have_duplicates_removed if not (x in seen or seen_add(x))]
