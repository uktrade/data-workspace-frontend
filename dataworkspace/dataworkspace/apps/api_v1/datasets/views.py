import json
import psycopg2
from django.http import StreamingHttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import SourceTable


def get_columns(connection, source_table):
    sql = psycopg2.sql.SQL('SELECT * from {}.{} LIMIT 0').format(
        psycopg2.sql.Identifier(source_table.schema),
        psycopg2.sql.Identifier(source_table.table),
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [c[0] for c in cursor.description]


def get_rows(connection, sql, query_args=None, cursor_itersize=1000):
    query_args = [] if query_args is None else query_args
    with connection.cursor() as cursor:
        cursor.itersize = cursor.itersize
        cursor.arraysize = cursor.itersize
        cursor.execute(sql, query_args)

        while True:
            rows = cursor.fetchmany(cursor_itersize)
            for row in rows:
                yield row
            if not rows:
                break


def get_primary_key(connection, schema, table):
    sql = psycopg2.sql.SQL(
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
        '''
    )

    with connection.cursor() as cursor:
        cursor.execute(sql, (schema, table))
        return [row[0] for row in cursor.fetchall()]


def len_chunk_header(num_chunk_bytes):
    return len('%X\r\n' % num_chunk_bytes)


def get_streaming_http_response(request, source_table):

    # StreamingHttpResponse translates to HTTP/1.1 chunking performed by gunicorn. However,
    # we don't have any visibility on the actual bytes sent as part of the HTTP body, i.e. each
    # chunk header and footer. We also don't appear to be able to work-around it and implement
    # our own chunked-encoder that makes these things visible. The best thing we can do is make
    # a good guess as to what these are, and add their lengths to the total number of bytes sent

    def yield_chunks(row_bytes):
        nonlocal queue
        nonlocal num_bytes_queued
        nonlocal num_bytes_sent
        nonlocal num_bytes_sent_and_queued

        queue.append(row_bytes)
        num_bytes_queued += len(row_bytes)
        num_bytes_sent_and_queued += len(row_bytes)
        while num_bytes_queued >= chunk_size:
            to_send_bytes = b''.join(queue)
            chunk, to_send_bytes = (
                to_send_bytes[:chunk_size],
                to_send_bytes[chunk_size:],
            )
            queue = [to_send_bytes] if to_send_bytes else []
            num_bytes_queued = len(to_send_bytes)
            num_bytes_sent += (
                len(chunk) + len_chunk_header(len(chunk)) + len_chunk_footer
            )
            yield chunk

    def yield_data(columns, rows, base_url):
        yield from yield_chunks(b'{"headers": ')
        yield from yield_chunks(json.dumps(columns).encode('utf-8'))
        yield from yield_chunks(b', "values": [')
        for i, row in enumerate(rows):
            row_bytes = json.dumps(row, default=str).encode('utf-8')
            if i > 0:
                row_bytes = b',' + row_bytes
            yield from yield_chunks(row_bytes)

            if num_bytes_sent_and_queued > num_bytes_max:
                search_after = [columns.index(k) for k in primary_key]
                search_after = [row[i] for i in search_after]
                search_after = '&'.join(
                    ['$searchAfter={}'.format(k) for k in search_after]
                )
                next_url = '{}?{}'.format(base_url, search_after)
                yield from yield_chunks(
                    b'], "next": "' + next_url.encode('utf-8') + b'"}'
                )
                break
        else:
            yield from yield_chunks(b'], "next": null}')
        yield from yield_remaining()

    def yield_remaining():
        if queue:
            yield b''.join(queue)

    num_bytes_max = 49990000
    len_chunk_footer = len('\r\n')
    chunk_size = 16384
    queue = []
    num_bytes_queued = 0
    num_bytes_sent = 0
    num_bytes_sent_and_queued = 0

    search_after = request.GET.getlist('$searchAfter')

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[source_table.database.memorable_name])
    ) as connection:
        primary_key = get_primary_key(
            connection, source_table.schema, source_table.table
        )

    if search_after == []:
        sql = psycopg2.sql.SQL(
            '''
                select
                    *

                from {}.{}

                order by {}
            '''
        ).format(
            psycopg2.sql.Identifier(source_table.schema),
            psycopg2.sql.Identifier(source_table.table),
            psycopg2.sql.SQL(',').join(map(psycopg2.sql.Identifier, primary_key)),
        )
    else:
        sql = psycopg2.sql.SQL(
            '''
                select
                    *

                from {}.{}

                where ({}) > ({})

                order by {}
            '''
        ).format(
            psycopg2.sql.Identifier(source_table.schema),
            psycopg2.sql.Identifier(source_table.table),
            psycopg2.sql.SQL(',').join(map(psycopg2.sql.Identifier, primary_key)),
            psycopg2.sql.SQL(',').join(psycopg2.sql.Placeholder() * len(search_after)),
            psycopg2.sql.SQL(',').join(map(psycopg2.sql.Identifier, primary_key)),
        )

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[source_table.database.memorable_name])
    ) as connection:
        columns = get_columns(connection, source_table)
        rows = get_rows(connection, sql, query_args=search_after)
        base_url = request.build_absolute_uri()
        return StreamingHttpResponse(
            yield_data(columns, rows, base_url),
            content_type='application/json',
            status=200,
        )


def dataset_api_view_GET(request, dataset_id, source_table_id):

    source_table = get_object_or_404(
        SourceTable, id=source_table_id, dataset__id=dataset_id
    )

    return get_streaming_http_response(request, source_table)
