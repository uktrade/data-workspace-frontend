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

    def __init__(self, connection, schema, table):
        self.column_names = []
        self.row_num = 0
        self.last_row = False

        self.cur = connection.cursor()

        sql_command = sql.SQL("""
                        SELECT
                            *
                        FROM
                            {}.{}
                    """).format(sql.Identifier(schema), sql.Identifier(table))

        logger.debug(sql_command)
        # TODO: Perhaps validate that this table exists and raise a custom error
        self.cur.execute(sql_command)

        for column_desc in self.cur.description:
            self.column_names.append(column_desc[0])
            logger.debug(column_desc[0])

    def __iter__(self):
        return self

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

    def __next__(self):
        self.row_num += 1
        if self.row_num == 1:
            return '['

        if self.last_row:
            raise StopIteration

        row = self.cur.fetchone()

        if row:
            json_text = self._get_row_as_json(row)
            return self._escape_row(json_text)

        self.last_row = True
        self.cur.close()
        return ']'


def reference_data_view(request, database, schema, table):
    results = ReferenceData.objects.filter(database__memorable_name=database, table_name=table,
                                       schema=schema)

    if not results:
        return HttpResponseForbidden()

    reference_data = results[0]
    logger.debug(f'found key_field is {reference_data.key_field_name}')

    with connect(database_dsn(settings.DATABASES_DATA[database])) as conn:
        reader = JsonReader(conn, schema, table)
        return StreamingHttpResponse(reader, content_type='application/json')
