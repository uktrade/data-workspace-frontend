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
import gevent
from psycopg2 import connect, sql
import requests

from app.models import (
    Database,
    Privilage,
)

logger = logging.getLogger('app')


def healthcheck_view(_):
    return HttpResponse('OK')


def databases_view(request):
    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseBadRequest(json.dumps({'detail': 'The Authorization header must be set.'})) if 'HTTP_AUTHORIZATION' not in request.META else \
        _databases(request.META['HTTP_AUTHORIZATION'])

    return response


def table_data_view(request, database, schema, table):
    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseUnauthorized() if not _can_access_table(request.user.email, database, schema, table) else \
        HttpResponseNotFound() if not _table_exists(database, schema, table) else \
        _table_data(database, schema, table)

    return response


def _can_access_table(email_address, database, schema, table):
    return any(
        True
        for privilage in _get_private_privilages(email_address)
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


def _table_data(database, schema, table):
    cursor_itersize = 1000
    bytes_queue = gevent.queue.Queue(maxsize=cursor_itersize)

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

            # There is no ordering here. We just want a full dump.
            # Also, there are not likely to be updates, so a long-running
            # query shouldn't cause problems with concurrency/locking
            cur.execute(sql.SQL("""
                SELECT
                    *
                FROM
                    {}.{}
            """).format(sql.Identifier(schema), sql.Identifier(table)))

            i = -1
            for i, row in enumerate(cur):
                if i == 0:
                    # Column names are not populated until the first row fetched
                    bytes_queue.put(csv_writer.writerow([column_desc[0] for column_desc in cur.description]))
                bytes_queue.put(csv_writer.writerow(row))

            bytes_queue.put(csv_writer.writerow('Number of rows: ' + str(i + 1)))

    def yield_bytes_from_queue():
        while put_db_rows_to_queue_job:
            try:
                # There will be a 0.1 second wait after the end of the data
                # from the db to when the connection is closed. Might be able
                # to avoid this, but KISS, and minor
                yield bytes_queue.get(timeout=0.1)
            except gevent.queue.Empty:
                pass

    put_db_rows_to_queue_job = gevent.spawn(put_db_rows_to_queue)

    response = StreamingHttpResponse(yield_bytes_from_queue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{schema}_{table}.csv"'
    return response


def _databases(auth):
    me_response = requests.get(settings.AUTHBROKER_URL + 'api/v1/user/me/', headers={
        'Authorization': auth,
    })
    databases_reponse = \
        JsonResponse({'databases': _public_databases() + _private_databases(me_response.json()['email'])}) if me_response.status_code == 200 else \
        HttpResponse(me_response.text, status=me_response.status_code)

    return databases_reponse


def _public_databases():
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


def _private_databases(email_address):
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
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        with \
                connect(_database_dsn(database_data)) as conn, \
                conn.cursor() as cur:

            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(sql.Identifier(user)), [password, tomorrow])
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
        'database__memorable_name', 'database__created_date', 'database__id',
    )


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401
