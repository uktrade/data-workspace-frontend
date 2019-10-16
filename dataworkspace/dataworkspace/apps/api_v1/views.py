import json
import logging
import re

import boto3

from django.conf import settings
from django.http import (
    JsonResponse,
    StreamingHttpResponse,
)

from psycopg2 import connect, sql

from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationTemplate
from dataworkspace.apps.applications.spawner import spawn
from dataworkspace.apps.applications.utils import (
    api_application_dict,
    application_api_is_allowed,
    application_template_and_data_from_host,
    get_api_visible_application_instance_by_public_host,
    set_application_stopped,
)
from dataworkspace.apps.core.utils import (
    can_access_table_by_google_data_studio,
    database_dsn,
)
from dataworkspace.apps.datasets.models import (
    SourceTable,
)
from dataworkspace.apps.core.utils import (
    create_s3_role,
    new_private_database_credentials,
)


SCHEMA_STRING = {
    'dataType': 'STRING',
    'semantics': {
        'conceptType': 'DIMENSION',
    },
}

SCHEMA_STRING_DATE = {
    'dataType': 'STRING',
    'semantics': {
        'conceptType': 'DIMENSION',
        'semanticType': 'YEAR_MONTH_DAY',
    },
}

SCHEMA_STRING_DATE_TIME = {
    'dataType': 'STRING',
    'semantics': {
        'conceptType': 'DIMENSION',
        'semanticType': 'YEAR_MONTH_DAY_SECOND',
    },
}

SCHEMA_BOOLEAN = {
    'dataType': 'BOOLEAN',
    'semantics': {
        'conceptType': 'DIMENSION',
    },
}

SCHEMA_NUMBER = {
    'dataType': 'NUMBER',
    'semantics': {
        'conceptType': 'METRIC',
    },
}

SCHEMA_DATA_TYPE_PATTERNS = (
    (
        r'^(character varying.*)|(text)|(text\[\])$',
        SCHEMA_STRING, lambda v: v),
    (
        r'^date$',
        SCHEMA_STRING_DATE, lambda v: v.strftime('%Y%m%d') if v is not None else None),
    (
        r'^timestamp.*$',
        SCHEMA_STRING_DATE_TIME, lambda v: v.strftime('%Y%m%d%H%M%S') if v is not None else None),
    (
        r'^boolean$',
        SCHEMA_BOOLEAN, lambda v: v),
    (
        r'^(bigint)|(decimal)|(integer)|(numeric)|(real)$',
        SCHEMA_NUMBER, lambda v: v),
)

logger = logging.getLogger('app')


def applications_api_view(request):
    return \
        applications_api_GET(request) if request.method == 'GET' else \
        JsonResponse({}, status=405)


def applications_api_GET(request):
    return JsonResponse({
        'applications': [
            api_application_dict(application)
            for application in ApplicationInstance.objects.filter(
                state__in=['RUNNING', 'SPAWNING'],
            )
        ]
    }, status=200)


def application_api_view(request, public_host):
    return \
        JsonResponse({}, status=403) if not application_api_is_allowed(request, public_host) else \
        application_api_GET(request, public_host) if request.method == 'GET' else \
        application_api_PUT(request, public_host) if request.method == 'PUT' else \
        application_api_PATCH(request, public_host) if request.method == 'PATCH' else \
        application_api_DELETE(request, public_host) if request.method == 'DELETE' else \
        JsonResponse({}, status=405)


def application_api_GET(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=404)

    return JsonResponse(api_application_dict(application_instance), status=200)


def application_api_PUT(request, public_host):
    # A transaction is unnecessary: the single_running_or_spawning_integrity
    # key prevents duplicate spawning/running applications at the same
    # public host
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        pass
    else:
        return JsonResponse({'message': 'Application instance already exists'}, status=409)

    try:
        application_template, public_host_data = application_template_and_data_from_host(public_host)
    except ApplicationTemplate.DoesNotExist:
        return JsonResponse({'message': 'Application template does not exist'}, status=400)

    credentials = new_private_database_credentials(request.user)

    try:
        memory, cpu = request.GET['__memory_cpu'].split('_')
    except KeyError:
        memory = None
        cpu = None

    application_instance = ApplicationInstance.objects.create(
        owner=request.user,
        application_template=application_template,
        spawner=application_template.spawner,
        spawner_application_template_options=application_template.spawner_options,
        spawner_application_instance_id=json.dumps({}),
        public_host=public_host,
        state='SPAWNING',
        single_running_or_spawning_integrity=public_host,
        cpu=cpu,
        memory=memory,
    )

    spawn.delay(
        application_template.spawner,
        request.user.email, str(request.user.profile.sso_id), public_host_data,
        application_instance.id, application_template.spawner_options, credentials)

    return JsonResponse(api_application_dict(application_instance), status=200)


def application_api_PATCH(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=404)

    state = json.loads(request.body)['state']

    if state != 'RUNNING':
        return JsonResponse({}, status=400)

    application_instance.state = state
    application_instance.save(update_fields=['state'])

    return JsonResponse({}, status=200)


def application_api_DELETE(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=200)

    set_application_stopped(application_instance)

    return JsonResponse({}, status=200)


def aws_credentials_api_view(request):
    return \
        aws_credentials_api_GET(request) if request.method == 'GET' else \
        JsonResponse({}, status=405)


def aws_credentials_api_GET(request):
    client = boto3.client('sts')
    role_arn, _ = create_s3_role(request.user.email, str(request.user.profile.sso_id))

    # Creating new credentials unfortunately sometimes fails
    max_attempts = 3
    for i in range(0, 3):
        try:
            credentials = client.assume_role(
                RoleArn=role_arn,
                RoleSessionName='s3_access_' + str(request.user.profile.sso_id),
                DurationSeconds=60 * 60,
            )['Credentials']
        except Exception:
            if i == max_attempts - 1:
                raise
        else:
            break

    return JsonResponse({
        'AccessKeyId': credentials['AccessKeyId'],
        'SecretAccessKey': credentials['SecretAccessKey'],
        'SessionToken': credentials['SessionToken'],
        'Expiration': credentials['Expiration']
    }, status=200)


def get_postgres_column_names_data_types(sourcetable):
    with \
            connect(database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])) as conn, \
            conn.cursor() as cur:
        cur.execute('''
            SELECT
                pg_attribute.attname AS column_name,
                pg_catalog.format_type(pg_attribute.atttypid, pg_attribute.atttypmod) AS data_type
            FROM
                pg_catalog.pg_attribute
            INNER JOIN
                pg_catalog.pg_class ON pg_class.oid = pg_attribute.attrelid
            INNER JOIN
                pg_catalog.pg_namespace ON pg_namespace.oid = pg_class.relnamespace
            WHERE
                pg_attribute.attnum > 0
                AND NOT pg_attribute.attisdropped
                AND pg_namespace.nspname = %s
                AND pg_class.relname = %s
            ORDER BY
                attnum ASC;
        ''', (sourcetable.schema, sourcetable.table))
        return cur.fetchall()


def schema_value_func_for_data_type(data_type):
    return next(
        (schema, value_func)
        for data_type_pattern, schema, value_func in SCHEMA_DATA_TYPE_PATTERNS
        if re.match(data_type_pattern, data_type)
    )


def schema_value_func_for_data_types(sourcetable):
    return [
        (
            {
                'name': column_name,
                'label': column_name.replace('_', ' ').capitalize(),
                **schema,
            },
            value_func,
        )
        for column_name, data_type in get_postgres_column_names_data_types(sourcetable)
        for schema, value_func in [schema_value_func_for_data_type(data_type)]
    ]


def get_schema(schema_value_funcs):
    return [
        schema
        for schema, _ in schema_value_funcs
    ]


def get_rows(sourcetable, schema_value_funcs):
    cursor_itersize = 1000

    with \
            connect(database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])) as conn, \
            conn.cursor(name='google_data_studio_all_table_data') as cur:  # Named cursor => server-side cursor

        cur.itersize = cursor_itersize
        cur.arraysize = cursor_itersize

        cur.execute(sql.SQL('''
            SELECT {} FROM {}.{}
        ''').format(
            sql.SQL(',').join([sql.Identifier(schema['name']) for schema, _ in schema_value_funcs]),
            sql.Identifier(sourcetable.schema),
            sql.Identifier(sourcetable.table)))

        while True:
            rows = cur.fetchmany(cursor_itersize)
            for row in rows:
                yield json.dumps({
                    'values': [
                        schema_value_funcs[i][1](value)
                        for i, value in enumerate(row)
                    ]
                }).encode('utf-8')
            if not rows:
                break


def table_api_schema_view(request, table_id):
    return \
        JsonResponse({}, status=403) if not request.user.is_superuser else \
        JsonResponse({}, status=403) if not can_access_table_by_google_data_studio(request.user, table_id) else \
        table_api_schema_POST(request, table_id) if request.method == 'POST' else \
        JsonResponse({}, status=405)


def table_api_schema_POST(request, table_id):
    # POST request to support HTTP bodies from Google Data Studio: it doesn't
    # seem to be able to send GETs with bodies
    sourcetable = SourceTable.objects.get(
        id=table_id,
    )
    schema_value_funcs = schema_value_func_for_data_types(sourcetable)
    return JsonResponse({
        'schema': get_schema(schema_value_funcs)
    }, status=200)


def table_api_rows_view(request, table_id):
    return \
        JsonResponse({}, status=403) if not request.user.is_superuser else \
        JsonResponse({}, status=403) if not can_access_table_by_google_data_studio(request.user, table_id) else \
        table_api_rows_POST(request, table_id) if request.method == 'POST' else \
        JsonResponse({}, status=405)


def table_api_rows_POST(request, table_id):
    # POST request to support HTTP bodies from Google Data Studio: it doesn't
    # seem to be able to send GETs with bodies
    sourcetable = SourceTable.objects.get(
        id=table_id,
    )
    column_names = [
        field['name']
        for field in json.loads(request.body)['fields']
    ]
    schema_value_funcs = [
        (schema, value_func)
        for schema, value_func in schema_value_func_for_data_types(sourcetable)
        if schema['name'] in column_names
    ]

    def yield_schema_and_rows_bytes():
        try:
            # Could be more optimised, e.g. combining yields to reduce socket
            # operations, but KISS
            yield b'{"schema":' + json.dumps(get_schema(schema_value_funcs)).encode('utf-8') + b',"rows":['

            later_row = False
            for row in get_rows(sourcetable, schema_value_funcs):
                if later_row:
                    yield b',' + row
                else:
                    yield row

                later_row = True

            yield b']}'
        except Exception:
            logger.exception('Error streaming to Google Data Studio')
            raise

    return StreamingHttpResponse(
        yield_schema_and_rows_bytes(), content_type='application/json', status=200)
