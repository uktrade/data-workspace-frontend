import json
import psycopg2
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from dataworkspace.apps.api_v1.views import (
    get_rows,
    get_schema,
    schema_value_func_for_data_types,
)
from dataworkspace.apps.datasets.models import SourceTable


def get_streaming_http_response(request, source_table):
    print('get_streaming_http_response')
    print('request.body:', request.body)

    # validate arguments
    try:
        request_dict = json.loads(request.body)
        fields = request_dict.pop('fields', [])
        column_names = [field['name'] for field in fields]
        search_after = request_dict.pop('$searchAfter')
        assert len(request_dict) == 0
    except (json.decoder.JSONDecodeError, KeyError, AssertionError) as e:
        errors = []
        if type(e) == AssertionError:
            for key in request_dict.keys():
                errors.append(f'invalid argument {key}')
        if len(errors) == 0:
            errors.append('invalid arguments, specify $searchAfter argument')
        return JsonResponse({'errors': errors}, status=400)

    def query_vars(fields_sql, schema_sql, table_sql, primary_key_sql):

        return (
            psycopg2.sql.SQL(
                'SELECT {},{} FROM {}.{} WHERE ({}) > ('
                + ','.join(['%s'] * len(search_after))
                + ') ORDER BY {}'
            ).format(
                primary_key_sql,
                fields_sql,
                schema_sql,
                table_sql,
                primary_key_sql,
                primary_key_sql,
            ),
            tuple(search_after),
        )

    schema_value_funcs = [
        (schema, value_func)
        for schema, value_func in schema_value_func_for_data_types(source_table)
        if schema['name'] in column_names or column_names == []
    ]

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

    def yield_schema_and_rows_bytes():
        try:
            yield from yield_chunks(
                b'{"headers":'
                + json.dumps(
                    [column['name'] for column in get_schema(schema_value_funcs)]
                ).encode('utf-8')
                + b',"values":['
            )

            for i, (row, search_after) in enumerate(
                get_rows(source_table, schema_value_funcs, query_vars)
            ):
                yield from yield_chunks(
                    # fmt: off
                    b',' + json.dumps(row['values']).encode('utf-8') if i != 0 else
                    json.dumps(row['values']).encode('utf-8')
                    # fmt: on
                )

                if num_bytes_sent_and_queued > num_bytes_max:
                    yield from yield_chunks(
                        b'],"$searchAfter":'
                        + json.dumps(search_after).encode('utf-8')
                        + b']}'
                    )
                    break
            else:
                yield from yield_chunks(b']}')

            yield from yield_remaining()
        except Exception as e:
            raise e

    return StreamingHttpResponse(
        yield_schema_and_rows_bytes(), content_type='application/json', status=200
    )


class APIDatasetView(APIView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    def post(self, request, dataset_id, source_table_id):

        print('api_dataset_view')
        source_table = get_object_or_404(
            SourceTable, id=source_table_id, dataset__id=dataset_id
        )

        return get_streaming_http_response(request, source_table)
