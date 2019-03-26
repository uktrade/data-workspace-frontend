import csv
import datetime
import itertools
import json
import logging
import re
import secrets
import string

from django.conf import (
    settings,
)
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.template import (
    loader,
)
import gevent
from psycopg2 import connect, sql
import requests

from app.models import (
    Database,
    Privilage,
)

logger = logging.getLogger('app')


def root_view(request):

    def tables_in_schema(cur, schema):
        logger.info('tables_in_schema: %s', schema)
        cur.execute("""
            SELECT
                tablename
            FROM
                pg_tables
            WHERE
                schemaname = %s
        """, (schema, ))
        results = [result[0] for result in cur.fetchall()]
        logger.info('tables_in_schema: %s %s', schema, results)
        return results

    def allowed_tables_for_database_that_exist(database, database_privilages):
        logger.info('allowed_tables_for_database_that_exist: %s %s', database, database_privilages)
        with \
                connect(_database_dsn(settings.DATABASES_DATA[database.memorable_name])) as conn, \
                conn.cursor() as cur:
            return [
                (database.memorable_name, privilage.schema, table)
                for privilage in database_privilages
                for table in tables_in_schema(cur, privilage.schema)
                if _can_access_table(database_privilages, database.memorable_name, privilage.schema, table)
            ]

    privilages = _get_private_privilages(request.user.email)
    privilages_by_database = itertools.groupby(privilages, lambda privilage: privilage.database)
    template = loader.get_template('root.html')
    context = {
        'database_schema_tables': _remove_duplicates(_flatten([
            allowed_tables_for_database_that_exist(database, list(database_privilages))
            for database, database_privilages in privilages_by_database
        ])),
        'notebooks_url': settings.NOTEBOOKS_URL,
        'appstream_url': settings.APPSTREAM_URL,
        'support_url': settings.SUPPORT_URL,
    }
    return HttpResponse(template.render(context, request))


def healthcheck_view(_):
    return HttpResponse('OK')


def databases_view(request):
    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseBadRequest(json.dumps({'detail': 'The Authorization header must be set.'})) if 'HTTP_AUTHORIZATION' not in request.META else \
        _databases(request.META['HTTP_AUTHORIZATION'])

    return response


def table_data_view(request, database, schema, table):
    logger.info('table_data_view attempt: %s %s %s %s', request.user.email, database, schema, table)
    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseUnauthorized() if not _can_access_table(_get_private_privilages(request.user.email), database, schema, table) else \
        HttpResponseNotFound() if not _table_exists(database, schema, table) else \
        _table_data(request.user.email, database, schema, table)

    return response


def _can_access_table(privilages, database, schema, table):
    return any(
        True
        for privilage in privilages
        for privilage_table in privilage.tables.split(',')
        if privilage.database.memorable_name == database and privilage.schema == schema and (privilage_table == table or privilage_table == 'ALL TABLES')
    )


def _table_exists(database, schema, table):
    with \
            connect(_database_dsn(settings.DATABASES_DATA[database])) as conn, \
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


def _table_data(user_email, database, schema, table):
    logger.info('table_data_view start: %s %s %s %s', user_email, database, schema, table)
    cursor_itersize = 1000
    queue_size = 5
    bytes_queue = gevent.queue.Queue(maxsize=queue_size)

    def put_db_rows_to_queue():
        # The csv writer "writes" its output by calling a file-like object
        # with a `write` method.
        class PseudoBuffer:
            def write(self, value):
                return value
        csv_writer = csv.writer(PseudoBuffer())

        with \
                connect(_database_dsn(settings.DATABASES_DATA[database])) as conn, \
                conn.cursor(name='all_table_data') as cur:  # Named cursor => server-side cursor

            cur.itersize = cursor_itersize
            cur.arraysize = cursor_itersize

            # There is no ordering here. We just want a full dump.
            # Also, there are not likely to be updates, so a long-running
            # query shouldn't cause problems with concurrency/locking
            cur.execute(sql.SQL("""
                SELECT
                    *
                FROM
                    {}.{}
            """).format(sql.Identifier(schema), sql.Identifier(table)))

            i = 0
            while True:
                rows = cur.fetchmany(cursor_itersize)
                if i == 0:
                    # Column names are not populated until the first row fetched
                    bytes_queue.put(csv_writer.writerow([column_desc[0] for column_desc in cur.description]), timeout=10)
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

        logger.info('table_data_view end: %s %s %s %s', user_email, database, schema, table)

    def handle_exception(job):
        try:
            raise job.exception
        except:
            logger.exception('table_data_view exception: %s %s %s %s', user_email, database, schema, table)

    put_db_rows_to_queue_job = gevent.spawn(put_db_rows_to_queue)
    put_db_rows_to_queue_job.link_exception(handle_exception)

    response = StreamingHttpResponse(yield_bytes_from_queue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{schema}_{table}.csv"'
    return response


def _databases(auth):
    me_response = requests.get(settings.AUTHBROKER_URL + 'api/v1/user/me/', headers={
        'Authorization': auth,
    })
    databases_reponse = \
        JsonResponse({'databases': _public_database_credentials() + _new_private_database_credentials(me_response.json()['email'])}) if me_response.status_code == 200 else \
        HttpResponse(me_response.text, status=me_response.status_code)

    return databases_reponse


def _public_database_credentials():
    return [{
        'memorable_name': database.memorable_name,
        'db_name': settings.DATABASES_DATA[database.memorable_name]['NAME'],
        'db_host': settings.DATABASES_DATA[database.memorable_name]['HOST'],
        'db_port': int(settings.DATABASES_DATA[database.memorable_name]['PORT']),
        'db_user': settings.DATABASES_DATA[database.memorable_name]['USER'],
        'db_password': settings.DATABASES_DATA[database.memorable_name]['PASSWORD'],
    } for database in Database.objects.all().filter(is_public=True).order_by(
        'memorable_name', 'created_date', 'id',
    )]


def _new_private_database_credentials(email_address):
    password_alphabet = string.ascii_letters + string.digits
    user_alphabet = string.ascii_lowercase + string.digits

    def postgres_user():
        unique_enough = ''.join(secrets.choice(user_alphabet) for i in range(5))
        return 'user_' + re.sub('[^a-z0-9]', '_', email_address.lower()) + '_' + unique_enough

    def postgres_password():
        return ''.join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, privilages_for_database):
        user = postgres_user()
        password = postgres_password()

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        with \
                connect(_database_dsn(database_data)) as conn, \
                conn.cursor() as cur:

            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(sql.Identifier(user)), [password, valid_until])
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(sql.Identifier(database_data['NAME']), sql.Identifier(user)))

            for privilage in privilages_for_database:
                cur.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(sql.Identifier(privilage.schema), sql.Identifier(user)))
                tables_sql_list = sql.SQL(',').join([
                    sql.SQL('{}.{}').format(sql.Identifier(privilage.schema), sql.Identifier(table))
                    for table in privilage.tables.split(',')
                ])
                tables_sql = \
                    sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {};').format(sql.Identifier(privilage.schema), sql.Identifier(user)) if privilage.tables == 'ALL TABLES' else \
                    sql.SQL('GRANT SELECT ON {} TO {};').format(tables_sql_list, sql.Identifier(user))
                cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': user,
            'db_password': password,
        }

    privilages = _get_private_privilages(email_address)

    return [
        get_new_credentials(database_obj, privilages_for_database)
        for database_obj, privilages_for_database in itertools.groupby(privilages, lambda privilage: privilage.database)
    ]


def _database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} ' \
        f'dbname={database_data["NAME"]} user={database_data["USER"]} ' \
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def _get_private_privilages(email_address):
    logger.info('Getting privilages for: %s', email_address)
    return Privilage.objects.all().filter(
        database__is_public=False,
        user__email=email_address,
    ).order_by(
        'database__memorable_name', 'schema', 'tables', 'id'
    )


def _flatten(to_flatten):
    return [
        item
        for sub_list in to_flatten
        for item in sub_list
    ]


def _remove_duplicates(to_have_duplicates_removed):
    seen = set()
    seen_add = seen.add
    return [x for x in to_have_duplicates_removed if not (x in seen or seen_add(x))]


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401
