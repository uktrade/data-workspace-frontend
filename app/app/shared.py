import datetime
import hashlib
import itertools
import logging
import re
import urllib.parse
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
)
import requests

from app.models import (
    DataSet,
    SourceTable,
)
from app.spawner import (
    get_spawner,
)

logger = logging.getLogger('app')


def database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} '
        f'dbname={database_data["NAME"]} user={database_data["USER"]} '
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def new_private_database_credentials(user):
    password_alphabet = string.ascii_letters + string.digits
    user_alphabet = string.ascii_lowercase + string.digits

    def postgres_user():
        unique_enough = ''.join(secrets.choice(user_alphabet) for i in range(5))
        return 'user_' + re.sub('[^a-z0-9]', '_', user.email.lower()) + '_' + unique_enough

    def postgres_password():
        return ''.join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, tables):
        user = postgres_user()
        password = postgres_password()

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.date.today() + datetime.timedelta(days=31)).isoformat()
        with connections[database_obj.memorable_name].cursor() as cur:
            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(
                sql.Identifier(user)), [password, valid_until])
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(
                sql.Identifier(database_data['NAME']), sql.Identifier(user)))

            for schema, table in tables:
                logger.info(
                    'Granting permissions to %s %s.%s to %s',
                    database_obj.memorable_name, schema, table, user)
                cur.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(
                    sql.Identifier(schema), sql.Identifier(user)))
                tables_sql = sql.SQL('GRANT SELECT ON {}.{} TO {};').format(
                    sql.Identifier(schema), sql.Identifier(table), sql.Identifier(user),
                )
                cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': user,
            'db_password': password,
        }

    database_to_tables = {
        database_obj: [
            (source_table.schema, source_table.table) for source_table in source_tables_for_database
        ]
        for database_obj, source_tables_for_database in itertools.groupby(source_tables_for_user(user), lambda source_table: source_table.database)
    }
    creds = [
        get_new_credentials(database_obj, tables)
        for database_obj, tables in database_to_tables.items()
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


def can_access_schema_table(user, database, schema, table):
    sourcetable = SourceTable.objects.filter(
        schema=schema,
        table=table,
        database__memorable_name=database,
    )
    has_source_table_perms = DataSet.objects.filter(
        Q(sourcetable__in=sourcetable) & (
            Q(user_access_type='REQUIRES_AUTHENTICATION') |
            Q(datasetuserpermission__user=user)
        ),
    ).exists()

    return has_source_table_perms


def source_tables_for_user(user):
    return SourceTable.objects.filter(
        Q(dataset__user_access_type='REQUIRES_AUTHENTICATION') |
        Q(dataset__datasetuserpermission__user=user)
    ).order_by('database__memorable_name', 'schema', 'table', 'id')


def stop_spawner_and_application(application_instance):
    get_spawner(application_instance.spawner).stop(
        application_instance.spawner_application_template_options,
        application_instance.spawner_application_instance_id,
    )
    set_application_stopped(application_instance)


def set_application_stopped(application_instance):
    application_instance.state = 'STOPPED'
    application_instance.single_running_or_spawning_integrity = str(application_instance.id)
    application_instance.save()


def application_instance_max_cpu(application_instance):
    # If we don't have the proxy url yet, we can't have any metrics yet.
    # This is expected and should not be shown as an error
    if application_instance.proxy_url is None:
        raise ValueError('Unknown')

    instance = urllib.parse.urlsplit(application_instance.proxy_url).hostname + ':8889'
    url = f'https://{settings.PROMETHEUS_DOMAIN}/api/v1/query'
    params = {
        'query': f'increase(precpu_stats__cpu_usage__total_usage{{instance="{instance}"}}[30s])[2h:30s]'
    }
    try:
        response = requests.get(url, params)
    except requests.RequestException:
        raise ValueError('Error connecting to metrics server')

    response_dict = response.json()
    if response_dict['status'] != 'success':
        raise ValueError(f'Metrics server return value is {response_dict["status"]}')

    try:
        values = response_dict['data']['result'][0]['values']
    except (IndexError, KeyError):
        # The server not having metrics yet should not be reported as an error
        raise ValueError(f'Unknown')

    max_cpu = 0.0
    ts_at_max = 0
    for ts, cpu in values:
        cpu_float = float(cpu) / (1000000000 * 30) * 100
        if cpu_float >= max_cpu:
            max_cpu = cpu_float
            ts_at_max = ts

    return max_cpu, ts_at_max
