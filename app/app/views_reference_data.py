import json
import logging

from django.conf import (
    settings,
)
from django.http import (
    StreamingHttpResponse,
    HttpResponseForbidden)

from django.shortcuts import (
    get_object_or_404,
)

from psycopg2 import (
    connect,
    sql,
)

from app.shared import database_dsn

from .models import (
    ReferenceData,
)

logger = logging.getLogger('app')


class JsonReader:
    def __init__(self, database, schema, table):
        database_connection_string = database_dsn(database)

        self.column_names = []
        self.row_num = 0
        self.last_row = False

        self.connection = connect(database_connection_string)
        self.cur = self.connection.cursor(name='server_side_cursor')

        sql_command = self._get_sql(schema, table)
        # TODO: Perhaps validate that this table exists and raise a custom error
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


def reference_data_view(request, database, schema, table):
    results = ReferenceData.objects.filter(database__memorable_name=database, table_name=table,
                                           schema=schema)

    if not results:
        return HttpResponseForbidden()

    reference_data = results[0]
    logger.debug(f'found key_field is {reference_data.key_field_name}')

    reader = JsonReader(settings.DATABASES_DATA[database], schema, table)
    return StreamingHttpResponse(reader, content_type='application/json')
