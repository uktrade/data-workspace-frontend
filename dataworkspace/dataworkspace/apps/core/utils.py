import datetime
import hashlib
import itertools
import logging
import random
import re
import secrets
import string
import csv

import gevent
import psycopg2
from psycopg2 import connect, sql

import boto3

from django.core.cache import cache
from django.http import StreamingHttpResponse
from django.db import connections, connection
from django.db.models import Q
from django.conf import settings

from dataworkspace.apps.datasets.models import DataSet, SourceTable, ReferenceDataset

logger = logging.getLogger('app')

USER_SCHEMA_STEM = '_user_'


def database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} '
        f'dbname={database_data["NAME"]} user={database_data["USER"]} '
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def postgres_user(stem, suffix=''):
    user_alphabet = string.ascii_lowercase + string.digits
    unique_enough = ''.join(secrets.choice(user_alphabet) for i in range(5))
    return (
        'user_'
        + re.sub('[^a-z0-9]', '_', stem.lower())
        + '_'
        + unique_enough
        + (f'_{suffix}' if suffix else '')
    )


def db_role_schema_suffix_for_user(user):
    return stable_identification_suffix(str(user.profile.sso_id), short=True)


def db_role_schema_suffix_for_app(application_template):
    return 'app_' + application_template.host_basename


def new_private_database_credentials(
    db_role_and_schema_suffix, source_tables, db_user, valid_for: datetime.timedelta,
):
    password_alphabet = string.ascii_letters + string.digits

    def postgres_password():
        return ''.join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, tables):
        # Each real-world user is given
        # - a private and permanent schema where they can manage tables and rows as needed
        # - a permanent database role that is the owner of the schema
        # - temporary database users, each of which are GRANTed the role

        db_password = postgres_password()
        # These must be the same so the below trigger can use a table's schema_name to set its role
        db_role = f'{USER_SCHEMA_STEM}{db_role_and_schema_suffix}'
        db_schema = f'{USER_SCHEMA_STEM}{db_role_and_schema_suffix}'

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.datetime.now() + valid_for).isoformat()

        with connections[database_obj.memorable_name].cursor() as cur:
            cur.execute(
                sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s').format(
                    sql.Identifier(db_user)
                ),
                [db_password, valid_until],
            )

        # Multiple concurrent GRANT CONNECT on the same database can cause
        # "tuple concurrently updated" errors
        with cache.lock(
            f'database-grant-connect-{database_data["NAME"]}--v4',
            blocking_timeout=3,
            timeout=180,
        ):
            with connections[database_obj.memorable_name].cursor() as cur:
                cur.execute(
                    sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(
                        sql.Identifier(database_data['NAME']), sql.Identifier(db_user)
                    )
                )

        with connections[database_obj.memorable_name].cursor() as cur:
            # ... create a role (if it doesn't exist)
            cur.execute(
                sql.SQL(
                    '''
                DO $$
                BEGIN
                  CREATE ROLE {};
                EXCEPTION WHEN OTHERS THEN
                  RAISE DEBUG 'Role {} already exists';
                END
                $$;
            '''
                ).format(sql.Identifier(db_role), sql.Identifier(db_role))
            )

            # ... add the user to the role
            cur.execute(
                sql.SQL('GRANT {} TO {};').format(
                    sql.Identifier(db_role), sql.Identifier(db_user)
                )
            )

            # ... create a schema
            cur.execute(
                sql.SQL('CREATE SCHEMA IF NOT EXISTS {};').format(
                    sql.Identifier(db_schema)
                )
            )

            # ... set the role to be the owner of the schema
            cur.execute(
                sql.SQL('ALTER SCHEMA {} OWNER TO {}').format(
                    sql.Identifier(db_schema), sql.Identifier(db_role)
                )
            )

            # ... and ensure new tables are owned by the role so all users of the role can access
            cur.execute(
                sql.SQL(
                    '''
                CREATE OR REPLACE FUNCTION set_table_owner()
                  RETURNS event_trigger
                  LANGUAGE plpgsql
                AS $$
                DECLARE
                  obj record;
                BEGIN
                  FOR obj IN
                    SELECT
                        * FROM pg_event_trigger_ddl_commands()
                    WHERE
                        command_tag IN ('ALTER TABLE', 'CREATE TABLE', 'CREATE TABLE AS')
                        -- Prevent infinite loop by not altering tables that have the correct owner
                        -- already. Note pg_trigger_depth() can be used for triggers, but we're in
                        -- an _event_ trigger.
                        AND left(schema_name, {}) = '{}'
                        AND (
                            SELECT pg_tables.tableowner
                            FROM pg_tables
                            WHERE pg_tables.schemaname = schema_name AND pg_tables.tablename = (
                                SELECT pg_class.relname FROM pg_class WHERE pg_class.oid = objid
                            )
                        ) != schema_name
                  LOOP
                    EXECUTE format('ALTER TABLE %s OWNER TO %s', obj.object_identity, quote_ident(obj.schema_name));
                  END LOOP;
                END;
                $$;
            '''.format(
                        str(len(USER_SCHEMA_STEM)), USER_SCHEMA_STEM
                    )
                )
            )
            cur.execute(
                '''
                DO $$
                BEGIN
                  CREATE EVENT TRIGGER set_table_owner
                  ON ddl_command_end
                  WHEN tag IN ('ALTER TABLE', 'CREATE TABLE', 'CREATE TABLE AS')
                  EXECUTE PROCEDURE set_table_owner();
                EXCEPTION WHEN OTHERS THEN
                  NULL;
                END $$;
            '''
            )

        with connections[database_obj.memorable_name].cursor() as cur:
            tables_that_exist = [
                (schema, table)
                for schema, table in tables
                if _table_exists(cur, schema, table)
            ]

        schemas = without_duplicates_preserve_order(
            schema for schema, _ in tables_that_exist
        )

        for schema in schemas:
            with cache.lock(
                f'database-grant--{database_data["NAME"]}--{schema}--v4',
                blocking_timeout=3,
                timeout=180,
            ):
                with connections[database_obj.memorable_name].cursor() as cur:
                    logger.info(
                        'Granting usages on %s %s to %s',
                        database_obj.memorable_name,
                        schema,
                        db_user,
                    )
                    cur.execute(
                        sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(
                            sql.Identifier(schema), sql.Identifier(db_user)
                        )
                    )

        for schema, table in tables_that_exist:
            with cache.lock(
                f'database-grant--{database_data["NAME"]}--{schema}--v4',
                blocking_timeout=3,
                timeout=180,
            ):
                with connections[database_obj.memorable_name].cursor() as cur:
                    logger.info(
                        'Granting permissions to %s %s.%s to %s',
                        database_obj.memorable_name,
                        schema,
                        table,
                        db_user,
                    )
                    tables_sql = sql.SQL('GRANT SELECT ON {}.{} TO {};').format(
                        sql.Identifier(schema),
                        sql.Identifier(table),
                        sql.Identifier(db_user),
                    )
                    cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_id': database_obj.id,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': db_user,
            'db_password': db_password,
        }

    database_to_tables = {
        database_obj: [
            (source_table['schema'], source_table['table'])
            for source_table in source_tables_for_database
        ]
        for database_obj, source_tables_for_database in itertools.groupby(
            source_tables, lambda source_table: source_table['database']
        )
    }
    creds = [
        get_new_credentials(database_obj, tables)
        for database_obj, tables in database_to_tables.items()
    ]

    return creds


def write_credentials_to_bucket(user, creds):
    logger.info('settings.NOTEBOOKS_BUCKET %s', settings.NOTEBOOKS_BUCKET)
    if settings.NOTEBOOKS_BUCKET is not None:
        bucket = settings.NOTEBOOKS_BUCKET
        s3_client = boto3.client('s3')
        s3_prefix = (
            'user/federated/'
            + stable_identification_suffix(str(user.profile.sso_id), short=False)
            + '/'
        )

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
                Q(user_access_type='REQUIRES_AUTHENTICATION')
                | Q(datasetuserpermission__user=user)
            )
        )
        .exists()
    )

    return has_source_table_perms


def can_access_table_by_google_data_studio(user, table_id):
    try:
        sourcetable = SourceTable.objects.get(
            id=table_id, accessible_by_google_data_studio=True
        )
    except SourceTable.DoesNotExist:
        return False
    has_source_table_perms = (
        DataSet.objects.live()
        .filter(
            Q(sourcetable=sourcetable)
            & (
                Q(user_access_type='REQUIRES_AUTHENTICATION')
                | Q(datasetuserpermission__user=user)
            )
        )
        .exists()
    )

    return has_source_table_perms


def source_tables_for_user(user):
    req_authentication_tables = SourceTable.objects.filter(
        dataset__user_access_type='REQUIRES_AUTHENTICATION',
        dataset__deleted=False,
        **{'dataset__published': True} if not user.is_superuser else {},
    )
    req_authorization_tables = SourceTable.objects.filter(
        dataset__user_access_type='REQUIRES_AUTHORIZATION',
        dataset__deleted=False,
        dataset__datasetuserpermission__user=user,
        **{'dataset__published': True} if not user.is_superuser else {},
    )
    source_tables = [
        {
            'database': x.database,
            'schema': x.schema,
            'table': x.table,
            'dataset': {
                'id': x.dataset.id,
                'name': x.dataset.name,
                'user_access_type': x.dataset.user_access_type,
            },
        }
        for x in req_authentication_tables.union(req_authorization_tables)
    ]
    reference_dataset_tables = [
        {
            'database': x.external_database,
            'schema': 'public',
            'table': x.table_name,
            'dataset': {
                'id': x.uuid,
                'name': x.name,
                'user_access_type': 'REQUIRES_AUTHENTICATION',
            },
        }
        for x in ReferenceDataset.objects.live()
        .filter(deleted=False, **{'published': True} if not user.is_superuser else {})
        .exclude(external_database=None)
    ]
    return source_tables + reference_dataset_tables


def source_tables_for_app(application_template):
    req_authentication_tables = SourceTable.objects.filter(
        dataset__published=True,
        dataset__deleted=False,
        dataset__user_access_type='REQUIRES_AUTHENTICATION',
    )
    req_authorization_tables = SourceTable.objects.filter(
        dataset__published=True,
        dataset__deleted=False,
        dataset__user_access_type='REQUIRES_AUTHORIZATION',
        dataset__datasetapplicationtemplatepermission__application_template=application_template,
    )
    source_tables = [
        {
            'database': x.database,
            'schema': x.schema,
            'table': x.table,
            'dataset': {
                'id': x.dataset.id,
                'name': x.dataset.name,
                'user_access_type': x.dataset.user_access_type,
            },
        }
        for x in req_authentication_tables.union(req_authorization_tables)
    ]
    reference_dataset_tables = [
        {
            'database': x.external_database,
            'schema': 'public',
            'table': x.table_name,
            'dataset': {
                'id': x.uuid,
                'name': x.name,
                'user_access_type': 'REQUIRES_AUTHENTICATION',
            },
        }
        for x in ReferenceDataset.objects.live()
        .filter(published=True, deleted=False)
        .exclude(external_database=None)
    ]
    return source_tables + reference_dataset_tables


def view_exists(database, schema, view):
    with connect(
        database_dsn(settings.DATABASES_DATA[database])
    ) as conn, conn.cursor() as cur:
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
            {'schema': schema, 'view': view},
        )
        return bool(cur.fetchone())


def table_exists(database, schema, table):
    with connect(
        database_dsn(settings.DATABASES_DATA[database])
    ) as conn, conn.cursor() as cur:
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


def streaming_query_response(user_email, database, query, filename):
    logger.info('streaming_query_response start: %s %s %s', user_email, database, query)
    batch_size = 1000
    query_timeout = 300 * 1000

    def yield_db_rows():
        # The csv writer "writes" its output by calling a file-like object
        # with a `write` method.
        class PseudoBuffer:
            def write(self, value):
                return value

        pseudo_buffer = PseudoBuffer()
        csv_writer = csv.writer(pseudo_buffer, quoting=csv.QUOTE_NONNUMERIC)

        with connect(
            database_dsn(settings.DATABASES_DATA[database])
        ) as conn, conn.cursor(
            name='data_download'
        ) as cur:  # Named cursor => server-side cursor

            conn.set_session(readonly=True)

            # set statements can't be issued in a server-side cursor, so we
            # need to create a separate one to set a timeout on the current
            # connection
            with conn.cursor() as _cur:
                _cur.execute('SET statement_timeout={0}'.format(query_timeout))

            cur.itersize = batch_size
            cur.arraysize = batch_size

            cur.execute(query)

            i = 0
            while True:
                rows = cur.fetchmany(batch_size)

                if i == 0:
                    # Column names are not populated until the first row fetched
                    yield csv_writer.writerow(
                        [column_desc[0] for column_desc in cur.description]
                    )

                if not rows:
                    break

                bytes_fetched = ''.join(
                    csv_writer.writerow(row) for row in rows
                ).encode('utf-8')

                yield bytes_fetched

                i += len(rows)

        yield csv_writer.writerow(['Number of rows: ' + str(i)])

        logger.info(
            'streaming_query_response end: %s %s %s', user_email, database, query
        )

    response = StreamingHttpResponseWithoutDjangoDbConnection(
        yield_db_rows(), content_type='text/csv'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


def get_random_data_sample(database, query, sample_size):
    query_timeout = 300 * 1000
    batch_size = sample_size * 100  # batch size to take sample from
    minimize_nulls_sample_size = sample_size * 2  # sample size before minimizing nulls

    with connect(database_dsn(settings.DATABASES_DATA[database])) as conn, conn.cursor(
        name='data_preview'
    ) as cur:  # Named cursor => server-side cursor

        conn.set_session(readonly=True)

        # set statements can't be issued in a server-side cursor, so we
        # need to create a separate one to set a timeout on the current
        # connection
        with conn.cursor() as _cur:
            _cur.execute('SET statement_timeout={0}'.format(query_timeout))

            try:
                cur.execute(query)
            except psycopg2.Error:
                logger.error("Failed to get sample data", exc_info=True)
                return []

        rows = cur.fetchmany(batch_size)
        sample = random.sample(rows, min(minimize_nulls_sample_size, len(rows)))
        sample.sort(
            key=lambda row: sum(value is not None for value in row), reverse=True
        )
        sample = sample[:sample_size]
        random.shuffle(sample)

        return sample


def table_data(user_email, database, schema, table, filename=None):
    # There is no ordering here. We just want a full dump.
    # Also, there are not likely to be updates, so a long-running
    # query shouldn't cause problems with concurrency/locking
    query = sql.SQL('SELECT * FROM {}.{}').format(
        sql.Identifier(schema), sql.Identifier(table)
    )
    if filename is None:
        filename = F'{schema}_{table}.csv'
    return streaming_query_response(user_email, database, query, filename)


def get_s3_prefix(user_sso_id):
    return (
        'user/federated/' + stable_identification_suffix(user_sso_id, short=False) + '/'
    )


def create_file_access_role(user_email_address, user_sso_id, access_point_id):
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
            role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
            logger.info(
                'User (%s) set up AWS role... done (%s)', user_email_address, role_arn
            )
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
                    '__S3_PREFIX__', s3_prefix
                ).replace('__ACCESS_POINT_ID__', access_point_id or ''),
            )
        except iam_client.exceptions.NoSuchEntityException:
            if i == max_attempts - 1:
                raise
            gevent.sleep(1)
        else:
            break

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
    #
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not connection.in_atomic_block:
            connection.close_if_unusable_or_obsolete()


def stable_identification_suffix(identifier, short):
    digest = hashlib.sha256(identifier.encode('utf-8')).hexdigest()
    if short:
        return digest[:8]
    return digest
