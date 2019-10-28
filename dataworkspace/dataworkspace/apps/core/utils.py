import datetime
import hashlib
import itertools
import logging
import re
import secrets
import string
import csv
import gevent
import gevent.queue
from psycopg2 import (
    connect,
    sql,
)

import boto3

from django.http import StreamingHttpResponse
from django.db import (
    connections,
)
from django.db.models import (
    Q,
)
from django.conf import (
    settings,
)

from dataworkspace.apps.datasets.models import (
    DataSet,
    SourceTable,
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
        # Each real-world user is given
        # - a private and permanent schema where they can manage tables and rows as needed
        # - a permanent database role that is the owner of the schema
        # - temporary database users, each of which are GRANTed the role

        db_user = postgres_user()
        db_password = postgres_password()
        short_sso_id = hashlib.sha256(str(user.profile.sso_id).encode('utf-8')).hexdigest()[:8]
        stem = '_user_'
        # These must be the same so the below trigger can use a table's schema_name to set its role
        db_role = f'{stem}{short_sso_id}'
        db_schema = f'{stem}{short_sso_id}'

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.date.today() + datetime.timedelta(days=31)).isoformat()
        with connections[database_obj.memorable_name].cursor() as cur:
            # Create a user...
            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(
                sql.Identifier(db_user)), [db_password, valid_until])
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(
                sql.Identifier(database_data['NAME']), sql.Identifier(db_user)))

            # ... create a role (if it doesn't exist)
            cur.execute(sql.SQL('''
                DO $$
                BEGIN
                  CREATE ROLE {};
                EXCEPTION WHEN OTHERS THEN
                  RAISE DEBUG 'Role {} already exists';
                END
                $$;
            ''').format(sql.Identifier(db_role), sql.Identifier(db_role)))

            # ... add the user to the role
            cur.execute(sql.SQL('GRANT {} TO {};').format(
                sql.Identifier(db_role), sql.Identifier(db_user),
            ))

            # ... create a schema
            cur.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {};').format(
                sql.Identifier(db_schema),
            ))

            # ... set the role to be the owner of the schema
            cur.execute(sql.SQL('ALTER SCHEMA {} OWNER TO {}').format(
                sql.Identifier(db_schema), sql.Identifier(db_role),
            ))

            # ... and ensure new tables are owned by the role so all users of the role can access
            cur.execute(sql.SQL('''
                CREATE OR REPLACE FUNCTION set_table_owner()
                  RETURNS event_trigger
                  LANGUAGE plpgsql
                AS $$
                DECLARE
                  obj record;
                BEGIN
                  FOR obj IN
                    SELECT * FROM pg_event_trigger_ddl_commands()
                    WHERE command_tag='CREATE TABLE' AND left(schema_name, {}) = '{}'
                  LOOP
                    EXECUTE format('ALTER TABLE %s OWNER TO %s', obj.object_identity, quote_ident(obj.schema_name));
                  END LOOP;
                END;
                $$;
            '''.format(str(len(stem)), stem)))
            cur.execute('''
                DO $$
                BEGIN
                  CREATE EVENT TRIGGER set_table_owner
                  ON ddl_command_end
                  WHEN tag IN ('CREATE TABLE')
                  EXECUTE PROCEDURE set_table_owner();
                EXCEPTION WHEN OTHERS THEN
                  NULL;
                END $$;
            ''')

            for schema, table in tables:
                logger.info(
                    'Granting permissions to %s %s.%s to %s',
                    database_obj.memorable_name, schema, table, db_user)
                cur.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(
                    sql.Identifier(schema), sql.Identifier(db_user)))
                tables_sql = sql.SQL('GRANT SELECT ON {}.{} TO {};').format(
                    sql.Identifier(schema), sql.Identifier(table), sql.Identifier(db_user),
                )
                cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': db_user,
            'db_password': db_password,
        }

    database_to_tables = {
        database_obj: [
            (source_table.schema, source_table.table) for source_table in source_tables_for_database
        ]
        for database_obj, source_tables_for_database in itertools.groupby(source_tables_for_user(user),
                                                                          lambda source_table: source_table.database)
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
        Q(published=True) &
        Q(sourcetable__in=sourcetable) & (
            Q(user_access_type='REQUIRES_AUTHENTICATION') |
            Q(datasetuserpermission__user=user)
        ),
    ).exists()

    return has_source_table_perms


def can_access_table_by_google_data_studio(user, table_id):
    try:
        sourcetable = SourceTable.objects.get(
            id=table_id,
            accessible_by_google_data_studio=True,
        )
    except SourceTable.DoesNotExist:
        return False
    has_source_table_perms = DataSet.objects.filter(
        Q(published=True) &
        Q(sourcetable=sourcetable) & (
            Q(user_access_type='REQUIRES_AUTHENTICATION') |
            Q(datasetuserpermission__user=user)
        ),
    ).exists()

    return has_source_table_perms


def source_tables_for_user(user):
    return SourceTable.objects.filter(
        Q(dataset__published=True) & (
            Q(dataset__user_access_type='REQUIRES_AUTHENTICATION') |
            Q(dataset__datasetuserpermission__user=user)
        )
    ).order_by('database__memorable_name', 'schema', 'table', 'id')


def view_exists(database, schema, view):
    with \
            connect(database_dsn(settings.DATABASES_DATA[database])) as conn, \
            conn.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM
                pg_catalog.pg_views
            WHERE
                schemaname = %s
            AND
                viewname = %s
        """, (schema, view))
        return bool(cur.fetchone())


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


def streaming_query_response(user_email, database, query, filename):
    logger.info('streaming_query_response start: %s %s %s', user_email, database, query)
    cursor_itersize = 1000
    queue_size = 3
    bytes_queue = gevent.queue.Queue(maxsize=queue_size)

    def put_db_rows_to_queue():
        # The csv writer "writes" its output by calling a file-like object
        # with a `write` method.
        class PseudoBuffer:
            def write(self, value):
                return value
        csv_writer = csv.writer(PseudoBuffer(), quoting=csv.QUOTE_NONNUMERIC)

        with \
                connect(database_dsn(settings.DATABASES_DATA[database])) as conn, \
                conn.cursor(name='all_table_data') as cur:  # Named cursor => server-side cursor

            conn.set_session(readonly=True)
            cur.itersize = cursor_itersize
            cur.arraysize = cursor_itersize

            try:
                cur.execute(query)
            except Exception as ex:
                gevent.get_hub().parent.throw(ex)

            i = 0
            while True:
                rows = cur.fetchmany(cursor_itersize)
                if i == 0:
                    # Column names are not populated until the first row fetched
                    bytes_queue.put(csv_writer.writerow(
                        [column_desc[0] for column_desc in cur.description]), timeout=10)
                bytes_fetched = ''.join(
                    csv_writer.writerow(row) for row in rows
                ).encode('utf-8')
                bytes_queue.put(bytes_fetched, timeout=15)
                i += len(rows)
                if not rows:
                    break
            bytes_queue.put(csv_writer.writerow(['Number of rows: ' + str(i)]))

    def yield_bytes_from_queue():
        while put_db_rows_to_queue_job:
            try:
                # There will be a 0.1 second wait after the end of the data
                # from the db to when the connection is closed. Might be able
                # to avoid this, but KISS, and minor
                yield bytes_queue.get(timeout=0.1)
            except gevent.queue.Empty:
                pass

        logger.info('streaming_query_response end: %s %s %s', user_email, database, query)

    def handle_exception(job):
        try:
            raise job.exception
        except Exception:
            logger.exception(
                'streaming_query_response exception: %s %s %s', user_email, database, query
            )

    put_db_rows_to_queue_job = gevent.spawn(put_db_rows_to_queue)
    put_db_rows_to_queue_job.link_exception(handle_exception)

    response = StreamingHttpResponse(yield_bytes_from_queue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def table_data(user_email, database, schema, table):
    # There is no ordering here. We just want a full dump.
    # Also, there are not likely to be updates, so a long-running
    # query shouldn't cause problems with concurrency/locking
    query = sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier(schema), sql.Identifier(table))
    return streaming_query_response(
        user_email, database, query, F'{schema}_{table}.csv'
    )


def get_s3_prefix(user_sso_id):
    return 'user/federated/' + hashlib.sha256(user_sso_id.encode('utf-8')).hexdigest() + '/'


def create_s3_role(user_email_address, user_sso_id):
    iam_client = boto3.client('iam')

    assume_role_policy_document = settings.S3_ASSUME_ROLE_POLICY_DOCUMENT
    policy_name = settings.S3_POLICY_NAME
    policy_document_template = settings.S3_POLICY_DOCUMENT_TEMPLATE
    permissions_boundary_arn = settings.S3_PERMISSIONS_BOUNDARY_ARN
    role_prefix = settings.S3_ROLE_PREFIX

    role_name = role_prefix + user_email_address
    s3_prefix = get_s3_prefix(user_sso_id)
    max_attempts = 10

    try:
        iam_client.create_role(
            RoleName=role_name,
            Path='/',
            AssumeRolePolicyDocument=assume_role_policy_document,
            PermissionsBoundary=permissions_boundary_arn,
        )
    except iam_client.exceptions.EntityAlreadyExistsException:
        # If the role already exists, we might need to update its assume role
        # policy document
        for i in range(0, max_attempts):
            try:
                iam_client.update_assume_role_policy(
                    RoleName=role_name,
                    PolicyDocument=assume_role_policy_document
                )
            except iam_client.exceptions.NoSuchEntityException:
                if i == max_attempts - 1:
                    raise
                gevent.sleep(1)
            else:
                break

    for i in range(0, max_attempts):
        try:
            role_arn = iam_client.get_role(
                RoleName=role_name
            )['Role']['Arn']
            logger.info('User (%s) set up AWS role... done (%s)', user_email_address, role_arn)
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
                PolicyDocument=policy_document_template.replace('__S3_PREFIX__', s3_prefix)
            )
        except iam_client.exceptions.NoSuchEntityException:
            if i == max_attempts - 1:
                raise
            gevent.sleep(1)
        else:
            break

    return role_arn, s3_prefix
