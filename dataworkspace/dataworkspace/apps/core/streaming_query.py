import csv
import logging
import queue

import gevent
from django.conf import settings
from psycopg2 import connect, sql

from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    database_dsn,
)

logger = logging.getLogger(__name__)


def new_streaming_query_response(
    user_email, database, filtered_query, unfiltered_query, filename, query_params=None
):
    logger.info('hacking streaming_query_response')
    batch_size = 1000
    query_timeout = 300 * 1000

    done = object()
    q = queue.Queue()

    def stream_query_as_csv_to_queue(conn):
        class PseudoBuffer:
            def write(self, value):
                return value

        pseudo_buffer = PseudoBuffer()
        csv_writer = csv.writer(pseudo_buffer, quoting=csv.QUOTE_NONNUMERIC)

        with conn.cursor(name='data_download') as cur:
            conn.set_session(readonly=True)
            # set statements can't be issued in a server-side cursor, so we
            # need to create a separate one to set a timeout on the current
            # connection
            with conn.cursor() as _cur:
                _cur.execute('SET statement_timeout={0}'.format(query_timeout))

            cur.itersize = batch_size
            cur.arraysize = batch_size
            cur.execute(filtered_query, vars=query_params)

            i = 0
            while True:
                rows = cur.fetchmany(batch_size)

                if i == 0:  # Column names are not populated until the first row fetched
                    logger.debug('write headers')
                    q.put(
                        csv_writer.writerow(
                            [column_desc[0] for column_desc in cur.description]
                        )
                    )

                if not rows:
                    logger.debug('no rows')
                    break

                logger.debug('data')
                bytes_fetched = ''.join(
                    csv_writer.writerow(row) for row in rows
                ).encode('utf-8')

                q.put(bytes_fetched)
                logger.debug(len(rows))
                i += len(rows)

            q.put(csv_writer.writerow(['Number of rows: ' + str(i)]))

        q.put(done)

    def get_all_columns_from_unfiltered(conn):
        logger.debug('get_all_columns_from_unfiltered')
        columns_query = sql.SQL('SELECT * FROM ({query}) as data LIMIT 1').format(
            query=unfiltered_query
        )
        with conn.cursor() as cur:
            cur.execute(columns_query)
            columns = [column_desc[0] for column_desc in cur.description]

        return columns

    def get_row_count_from_unfiltered(conn):
        logger.debug('get_row_count_from_unfiltered')
        total_query = sql.SQL('SELECT COUNT(*) from ({query}) as data;').format(
            query=unfiltered_query,
        )

        with conn.cursor() as cur:
            cur.execute(total_query)

            counts = cur.fetchone()
            logger.info(counts)

        return counts

    def steam_csv_and_calculate_totals():
        with connect(database_dsn(settings.DATABASES_DATA[database])) as conn:
            stream_query_as_csv_to_queue(conn)

            all_columns = get_all_columns_from_unfiltered(conn)
            counts = get_row_count_from_unfiltered(conn)

        logger.debug(all_columns)
        logger.debug(counts)

    def csv_iterator():
        # Listen for all data on the queue until we receive the done object
        # this means that the filtered part of the query is complete
        # and we can return
        while True:
            data = q.get(block=True)

            if data == done:
                logger.info("done")
                break

            if data:
                logger.info("q data")
                yield data

            q.task_done()

    def exception_callback(g):
        try:
            g.get()
        except Exception as e:
            logger.error(e, exc_info=True)
            raise

    g = gevent.spawn(steam_csv_and_calculate_totals)
    g.link_exception(exception_callback)

    response = StreamingHttpResponseWithoutDjangoDbConnection(
        csv_iterator(), content_type='text/csv',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
