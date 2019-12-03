import json
import psycopg2
from django.http import StreamingHttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import SourceTable


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


def get_streaming_http_response(request, source_table):

    search_after = request.GET.getlist('$searchAfter')

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[source_table.database.memorable_name])
    ) as connection:
        primary_key = get_primary_key(
            connection, source_table.schema, source_table.table
        )

    if search_after == []:
        where_clause = ''
        query_args = []
    else:
        where_clause = 'where ({}) > ({})'.format(
            ','.join(primary_key), ','.join(['%s' for i in range(len(search_after))])
        )
        query_args = search_after

    sql = psycopg2.sql.SQL(
        '''
        select
            *

        from {schema}.{table}

        {where_clause}

        order by ({primary_key})

        '''.format(
            schema=source_table.schema,
            table=source_table.table,
            primary_key=','.join(primary_key),
            where_clause=where_clause,
        )
    )

    # https://developers.google.com/apps-script/guides/services/quotas#current_limitations
    # URL Fetch response size: 50mb, and a bit of a buffer for http headers and $searchAfter
    num_bytes_max = 49990000

    # StreamingHttpResponse translates to HTTP/1.1 chunking performed by gunicorn. However,
    # we don't have any visibility on the actual bytes sent as part of the HTTP body, i.e. each
    # chunk header and footer. We also don't appear to be able to work-around it and implement
    # our own chunked-encoder that makes these things visible. The best thing we can do is make
    # a good guess as to what these are, and add their lengths to the total number of bytes sent
    def len_chunk_header(num_chunk_bytes):
        return len('%X\r\n' % num_chunk_bytes)

    len_chunk_footer = len('\r\n')

    chunk_size = 16384
    queue = []
    num_bytes_queued = 0
    num_bytes_sent = 0
    num_bytes_sent_and_queued = 0

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

    def yield_remaining():
        if queue:
            yield b''.join(queue)

    def get_rows(connection, sql, query_args=None, cursor_itersize=1000):
        query_args = [] if query_args is None else query_args
        with connection.cursor() as cursor:
            cursor.itersize = cursor.itersize
            cursor.arraysize = cursor.itersize
            cursor.execute(sql, query_args)
            columns = [c[0] for c in cursor.description]

            while True:
                rows = cursor.fetchmany(cursor_itersize)
                for row in rows:
                    yield row, columns
                if not rows:
                    break

    def yield_data(connection):

        for i, (row, columns) in enumerate(
            get_rows(connection, sql, query_args=query_args)
        ):
            if i == 0:
                yield from yield_chunks(
                    b'{"headers": '
                    + json.dumps(columns).encode('utf-8')
                    + b', "values": ['
                    + json.dumps(row).encode('utf-8')
                )
            else:
                yield from yield_chunks(b',' + json.dumps(row).encode('utf-8'))

            if num_bytes_sent_and_queued > num_bytes_max:
                search_after = [columns.index(k) for k in primary_key]
                search_after = [row[i] for i in search_after]
                search_after = '&'.join(
                    ['$searchAfter={}'.format(k) for k in search_after]
                )
                next_url = '{}?{}'.format(request.build_absolute_uri(), search_after)
                yield from yield_chunks(
                    b'], "next": "' + next_url.encode('utf-8') + b'"}'
                )
                break
        else:
            yield from yield_chunks(b']}')
        yield from yield_remaining()

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[source_table.database.memorable_name])
    ) as connection:
        return StreamingHttpResponse(
            yield_data(connection), content_type='application/json', status=200
        )


def dataset_api_view_GET(request, dataset_id, source_table_id):

    source_table = get_object_or_404(
        SourceTable, id=source_table_id, dataset__id=dataset_id
    )

    return get_streaming_http_response(request, source_table)
