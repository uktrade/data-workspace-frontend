import json, psycopg2, re
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.pagination import CursorPagination
from rest_framework.views import APIView
from dataworkspace.apps.datasets.models import SourceTable
from dataworkspace.apps.core.utils import database_dsn
from django.conf import settings


def get_postgres_column_names_data_types(sourcetable):
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor() as cur:
        cur.execute(
            '''
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
        ''',
            (sourcetable.schema, sourcetable.table),
        )
        return cur.fetchall()


def get_primary_keys(connection, table, schema='public'):
    sql = '''
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
    '''
    with connection.cursor() as cursor:
        cursor.execute(sql, [schema, table])
        rows = cursor.fetchall()
    return [row[0] for row in rows]

def get_rows(sourcetable, schema_value_funcs, pagination):
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
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor() as cur:

        cur.execute(
            '''
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
        ''',
            (sourcetable.schema, sourcetable.table),
        )
        primary_key_column_names = [row[0] for row in cur.fetchall()]

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[sourcetable.database.memorable_name])
    ) as conn, conn.cursor(
        name='google_data_studio_all_table_data'
    ) as cur:  # Named cursor => server-side cursor

        cur.itersize = cursor_itersize
        cur.arraysize = cursor_itersize

        fields_sql = psycopg2.sql.SQL(',').join(
            [psycopg2.sql.Identifier(schema['name']) for schema, _ in schema_value_funcs]
        )
        primary_key_sql = psycopg2.sql.SQL(',').join(
            [psycopg2.sql.Identifier(column_name) for column_name in primary_key_column_names]
        )
        schema_sql = psycopg2.sql.Identifier(sourcetable.schema)
        table_sql = psycopg2.sql.Identifier(sourcetable.table)

        def query_var_non_paginated():
            return (
                psycopg2.sql.SQL(
                    '''
                SELECT {} FROM {}.{} ORDER BY {}
            '''
                ).format(fields_sql, schema_sql, table_sql, primary_key_sql),
                (),
            )

        def query_vars_paginated():
            limit = int(pagination['rowCount'])
            offset = (
                int(pagination['startRow']) - 1
            )  # Google Data Studio start is 1-indexed
            return (
                psycopg2.sql.SQL(
                    '''
                SELECT {} FROM {}.{} ORDER BY {} LIMIT %s OFFSET %s
            '''
                ).format(fields_sql, schema_sql, table_sql, primary_key_sql),
                (limit, offset),
            )

        query_sql, vars_sql = (
            query_var_non_paginated() if pagination is None else query_vars_paginated()
        )

        cur.execute(query_sql, vars_sql)

        while True:
            rows = cur.fetchmany(cursor_itersize)
            print('\033[34mrows\033[0m:', rows)
            # for row in rows:
            #     yield json.dumps(
            #         {
            #             'values': [
            #                 schema_value_funcs[i][1](value)
            #                 for i, value in enumerate(row)
            #             ]
            #         }
            #     ).encode('utf-8')
            if not rows:
                break
            yield json.dumps(rows).encode('utf-8')

def get_schema(schema_value_funcs):
    return [schema for schema, _ in schema_value_funcs]

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


SCHEMA_STRING = {'dataType': 'STRING', 'semantics': {'conceptType': 'DIMENSION'}}

SCHEMA_STRING_DATE = {
    'dataType': 'STRING',
    'semantics': {'conceptType': 'DIMENSION', 'semanticType': 'YEAR_MONTH_DAY'},
}

SCHEMA_STRING_DATE_TIME = {
    'dataType': 'STRING',
    'semantics': {'conceptType': 'DIMENSION', 'semanticType': 'YEAR_MONTH_DAY_SECOND'},
}

SCHEMA_BOOLEAN = {'dataType': 'BOOLEAN', 'semantics': {'conceptType': 'DIMENSION'}}

SCHEMA_NUMBER = {'dataType': 'NUMBER', 'semantics': {'conceptType': 'METRIC'}}

SCHEMA_DATA_TYPE_PATTERNS = (
    (r'^(character varying.*)|(text)$', SCHEMA_STRING, lambda v: v),
    (r'^(uuid)$', SCHEMA_STRING, str),
    (
        # Not sure if this is suitable for Google Data Studio analysis, but avoids the error if
        # passing an array as a value:
        # "The data returned from the community connector is malformed"
        r'^text\[\]$',
        SCHEMA_STRING,
        ','.join,
    ),
    (
        r'^date$',
        SCHEMA_STRING_DATE,
        lambda v: v.strftime('%Y%m%d') if v is not None else None,
    ),
    (
        r'^timestamp.*$',
        SCHEMA_STRING_DATE_TIME,
        lambda v: v.strftime('%Y%m%d%H%M%S') if v is not None else None,
    ),
    (r'^boolean$', SCHEMA_BOOLEAN, lambda v: v),
    (r'^(bigint)|(decimal)|(integer)|(numeric)|(real)$', SCHEMA_NUMBER, lambda v: v),
)


class Pagination(CursorPagination):
    ordering = ('id',)
    offset_cutoff = None


class APIDatasetView(APIView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    cursor_itersize = 1000 #todo make this configurable
    cursor_arraysize = 1000 #todo make this configurable
    
    def get(self, request, dataset_id, source_table_id):
        pagination = None
        source_table = get_object_or_404(
            SourceTable,
            id=source_table_id,
            dataset__id=dataset_id
        )

        column_names = []
        
        schema_value_funcs = [
            (schema, value_func)
            for schema, value_func in schema_value_func_for_data_types(source_table)
            if schema['name'] in column_names or column_names == []
        ]
        def yield_schema_and_row_bytes():
            yield b'{"headers":' + json.dumps(
                [x['name'] for x in get_schema(schema_value_funcs)]
            ).encode(
                'utf-8'
            ) + b',"values":'

            later_row = False
            for row in get_rows(source_table, schema_value_funcs, pagination):
                if later_row:
                    yield b',' + row
                else:
                    yield row
                later_row = True
            yield b'}'

        return StreamingHttpResponse(
            yield_schema_and_row_bytes(), content_type='application/json', status=200,
        )
