import json
import logging

from django.conf import (
    settings,
)
from django.http import (
    StreamingHttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
)

from django.views.decorators.http import require_GET

from psycopg2 import (
    connect,
    sql,
)

from app.shared import database_dsn, table_exists

from .models import (
    ReferenceData,
)

logger = logging.getLogger('app')


class JsonWriter:
    def __init__(self, reference_data):
        database = settings.DATABASES_DATA[reference_data.database.memorable_name]
        database_connection_string = database_dsn(database)

        self.column_names = []
        self.row_num = 0
        self.last_row = False

        self.connection = connect(database_connection_string)
        self.cur = self.connection.cursor(name='server_side_cursor')

        sql_command = self._get_sql(reference_data.schema, reference_data.table_name)
        self.cur.execute(sql_command)

    def __iter__(self):
        return self

    def _get_sql(self, schema, table):
        return sql.SQL("""
                                SELECT
                                    *
                                FROM
                                    {}.{}
                            """).format(sql.Identifier(schema), sql.Identifier(table))

    def _get_row_as_json(self, row):
        result = {}
        for i in range(len(self.column_names)):
            result[self.column_names[i]] = str(row[i])

        return json.dumps(result)

    def _escape_row(self, json_text):
        prefix = ','

        if self.row_num == 2:
            prefix = ''

        return f'{prefix}{json_text}'

    def _read_column_names(self):
        for column_desc in self.cur.description:
            self.column_names.append(column_desc[0])
            logger.debug(column_desc[0])

    def __next__(self):
        self.row_num += 1
        if self.row_num == 1:
            return '['

        if self.last_row:
            raise StopIteration

        row = self.cur.fetchone()

        if row:
            if self.row_num == 2:
                self._read_column_names()

            json_text = self._get_row_as_json(row)
            return self._escape_row(json_text)

        self.last_row = True
        self.cur.close()
        self.connection.close()
        return ']'


@require_GET
def reference_data_view(request, database, schema, table):
    response = _get_json_as_streaming_response(database, schema, table)
    # not sure if requirements are for a downloadable file
    # response['Content-Disposition'] = f'attachment; filename="{schema}_{table}.json"'

    return response


def _get_json_as_streaming_response(database, schema, table):
    results = ReferenceData.objects.filter(database__memorable_name=database, table_name=table,
                                           schema=schema)

    if not results:
        return HttpResponseForbidden()

    if not table_exists(database, schema, table):
        return HttpResponseNotFound()

    reference_data = results[0]
    reader = JsonWriter(reference_data)

    # pylint suggests that we use jsonresponse but that doesn't support streaming
    # pylint: disable=R5102
    response = StreamingHttpResponse(reader, content_type='application/json')
    return response
