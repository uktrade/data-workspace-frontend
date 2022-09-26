import json
import logging
import re

import gevent

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import JsonResponse

from psycopg2 import connect, sql

from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
    UserToolConfiguration,
)
from dataworkspace.apps.applications.spawner import spawn
from dataworkspace.apps.applications.utils import (
    api_application_dict,
    application_options,
    application_api_is_allowed,
    application_template_tag_user_commit_from_host,
    get_api_visible_application_instance_by_public_host,
    set_application_stopped,
)
from dataworkspace.apps.core.boto3_client import get_sts_client
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.core.utils import create_tools_access_iam_role


SCHEMA_STRING = {"dataType": "STRING", "semantics": {"conceptType": "DIMENSION"}}

SCHEMA_STRING_DATE = {
    "dataType": "STRING",
    "semantics": {"conceptType": "DIMENSION", "semanticType": "YEAR_MONTH_DAY"},
}

SCHEMA_STRING_DATE_TIME = {
    "dataType": "STRING",
    "semantics": {"conceptType": "DIMENSION", "semanticType": "YEAR_MONTH_DAY_SECOND"},
}

SCHEMA_BOOLEAN = {"dataType": "BOOLEAN", "semantics": {"conceptType": "DIMENSION"}}

SCHEMA_NUMBER = {"dataType": "NUMBER", "semantics": {"conceptType": "METRIC"}}

SCHEMA_DATA_TYPE_PATTERNS = (
    (r"^(character varying.*)|(text)$", SCHEMA_STRING, lambda v: v),
    (r"^(uuid)$", SCHEMA_STRING, str),
    (
        # Not sure if this is suitable for Google Data Studio analysis, but avoids the error if
        # passing an array as a value:
        # "The data returned from the community connector is malformed"
        r"^text\[\]$",
        SCHEMA_STRING,
        ",".join,
    ),
    (
        r"^date$",
        SCHEMA_STRING_DATE,
        lambda v: v.strftime("%Y%m%d") if v is not None else None,
    ),
    (
        r"^timestamp.*$",
        SCHEMA_STRING_DATE_TIME,
        lambda v: v.strftime("%Y%m%d%H%M%S") if v is not None else None,
    ),
    (r"^boolean$", SCHEMA_BOOLEAN, lambda v: v),
    (
        r"^(bigint)|(decimal)|(integer)|(numeric)|(real)|(double precision)$",
        SCHEMA_NUMBER,
        lambda v: v,
    ),
)

logger = logging.getLogger("app")


def applications_api_view(request):
    return (
        applications_api_GET(request) if request.method == "GET" else JsonResponse({}, status=405)
    )


def applications_api_GET(request):
    return JsonResponse(
        {
            "applications": [
                api_application_dict(application)
                for application in ApplicationInstance.objects.filter(
                    state__in=["RUNNING", "SPAWNING"]
                )
            ]
        },
        status=200,
    )


def application_api_view(request, public_host):
    # Check if a custom permission denied error was thrown. If it was return the context
    # specific error page to the proxy. Otherwise, fall back to the standard 403 error page.
    try:
        is_allowed = application_api_is_allowed(request, public_host)
    except PermissionDenied as e:
        return JsonResponse({"redirect_url": getattr(e, "redirect_url", "/error_403")}, status=403)

    return (
        JsonResponse({"redirect_url": "/error_403"}, status=403)
        if not is_allowed
        else application_api_GET(request, public_host)
        if request.method == "GET"
        else application_api_PUT(request, public_host)
        if request.method == "PUT"
        else application_api_PATCH(request, public_host)
        if request.method == "PATCH"
        else application_api_DELETE(request, public_host)
        if request.method == "DELETE"
        else JsonResponse({}, status=405)
    )


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
        return JsonResponse({"message": "Application instance already exists"}, status=409)

    try:
        (
            application_template,
            tag,
            _,
            commit_id,
        ) = application_template_tag_user_commit_from_host(public_host)
    except ApplicationTemplate.DoesNotExist:
        return JsonResponse({"message": "Application template does not exist"}, status=400)

    app_type = application_template.application_type

    if app_type == "TOOL":
        tool_configuration = (
            application_template.user_tool_configuration.filter(user=request.user).first()
            or UserToolConfiguration.default_config()
        )
        cpu = tool_configuration.size_config.cpu
        memory = tool_configuration.size_config.memory
    else:
        cpu = application_template.default_cpu
        memory = application_template.default_memory

    spawner_options = json.dumps(application_options(application_template))

    try:
        application_instance = ApplicationInstance.objects.create(
            owner=request.user,
            application_template=application_template,
            spawner=application_template.spawner,
            spawner_application_template_options=spawner_options,
            spawner_application_instance_id=json.dumps({}),
            public_host=public_host,
            state="SPAWNING",
            single_running_or_spawning_integrity=public_host,
            cpu=cpu,
            memory=memory,
            commit_id=commit_id,
        )
    except IntegrityError:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    else:
        spawn.delay(
            application_template.spawner,
            request.user.pk,
            tag,
            application_instance.id,
            spawner_options,
        )

    return JsonResponse(api_application_dict(application_instance), status=200)


def application_api_PATCH(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=404)

    state = json.loads(request.body)["state"]

    if state != "RUNNING":
        return JsonResponse({}, status=400)

    application_instance.state = state
    application_instance.save(update_fields=["state"])

    return JsonResponse({}, status=200)


def application_api_DELETE(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=200)

    set_application_stopped(application_instance)

    return JsonResponse({}, status=200)


def aws_credentials_api_view(request):
    return (
        aws_credentials_api_GET(request)
        if request.method == "GET"
        else JsonResponse({}, status=405)
    )


def aws_credentials_api_GET(request):
    client = get_sts_client()
    role_arn, _ = create_tools_access_iam_role(
        request.user.email,
        request.user.profile.home_directory_efs_access_point_id,
    )

    # Creating new credentials unfortunately sometimes fails
    max_attempts = 3
    for i in range(0, 3):
        try:
            credentials = client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="s3_access_" + str(request.user.profile.sso_id),
                DurationSeconds=60 * 60,
            )["Credentials"]
        except Exception:  # pylint: disable=broad-except
            if i == max_attempts - 1:
                raise
        else:
            # To try compensating for eventual consistency
            gevent.sleep(1)
            break

    return JsonResponse(
        {
            "AccessKeyId": credentials["AccessKeyId"],
            "SecretAccessKey": credentials["SecretAccessKey"],
            "SessionToken": credentials["SessionToken"],
            "Expiration": credentials["Expiration"],
        },
        status=200,
    )


def get_postgres_column_names_data_types(sourcetable):
    with connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor() as cur:
        cur.execute(
            """
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
        """,
            (sourcetable.schema, sourcetable.table),
        )
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
                "name": column_name,
                "label": column_name.replace("_", " ").capitalize(),
                **schema,
            },
            value_func,
        )
        for column_name, data_type in get_postgres_column_names_data_types(sourcetable)
        for schema, value_func in [schema_value_func_for_data_type(data_type)]
    ]


def get_schema(schema_value_funcs):
    return [schema for schema, _ in schema_value_funcs]


def get_rows(sourcetable, schema_value_funcs, query_var):
    cursor_itersize = 1000

    # Order the rows by primary key so
    # - multiple requests are consistent with each other;
    # - and specifically and more importantly, sopaginated results are
    #   consistent with each other
    # We make no assumption on the name or number of columns in the primary
    # key, other than it exists
    # We _could_ use `oid` to order rows if there is no primary key, but we
    # would like all tables to have a primary key, so we deliberately don't
    # implement this
    with connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor() as cur:

        cur.execute(
            """
            SELECT
                pg_attribute.attname AS column_name
            FROM
                pg_catalog.pg_class pg_class_table
            INNER JOIN
                pg_catalog.pg_index ON pg_index.indrelid = pg_class_table.oid
            INNER JOIN
                pg_catalog.pg_class pg_class_index ON pg_class_index.oid = pg_index.indexrelid
            INNER JOIN
                pg_catalog.pg_namespace ON pg_namespace.oid = pg_class_table.relnamespace
            INNER JOIN
                pg_catalog.pg_attribute ON pg_attribute.attrelid = pg_class_index.oid
            WHERE
                pg_namespace.nspname = %s
                AND pg_class_table.relname = %s
                AND pg_index.indisprimary
            ORDER BY
                pg_attribute.attnum
        """,
            (sourcetable.schema, sourcetable.table),
        )
        primary_key_column_names = [row[0] for row in cur.fetchall()]

    with connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor(
        name="google_data_studio_all_table_data"
    ) as cur:  # Named cursor => server-side cursor

        cur.itersize = cursor_itersize
        cur.arraysize = cursor_itersize

        fields_sql = sql.SQL(",").join(
            [sql.Identifier(schema["name"]) for schema, _ in schema_value_funcs]
        )
        primary_key_sql = sql.SQL(",").join(
            [sql.Identifier(column_name) for column_name in primary_key_column_names]
        )
        schema_sql = sql.Identifier(sourcetable.schema)
        table_sql = sql.Identifier(sourcetable.table)

        query_sql, vars_sql = query_var(fields_sql, schema_sql, table_sql, primary_key_sql)
        cur.execute(query_sql, vars_sql)

        while True:
            rows = cur.fetchmany(cursor_itersize)
            for row in rows:
                primary_key_values = row[: len(primary_key_column_names)]
                requested_field_values = row[len(primary_key_column_names) :]
                values = [
                    schema_value_funcs[i][1](value)
                    for i, value in enumerate(requested_field_values)
                ]
                yield {"values": values}, primary_key_values
            if not rows:
                break
