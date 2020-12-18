import csv
import json
import string
import uuid
from datetime import datetime
from io import BytesIO, StringIO

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.module_loading import import_string
from django.utils.text import slugify

from dataworkspace.apps.explorer.tasks import execute_query
from dataworkspace.apps.explorer.utils import fetch_query_results


def get_exporter_class(format_):
    class_str = dict(settings.EXPLORER_DATA_EXPORTERS)[format_]
    return import_string(class_str)


class BaseExporter:
    name = ''
    content_type = ''
    file_extension = ''

    def __init__(self, query, user):
        self.query = query
        self.user = user

    def get_output(self, **kwargs):
        value = self.get_file_output(**kwargs).getvalue()
        return value

    def get_file_output(self, **kwargs):
        query_log_id = execute_query.delay(
            self.query.final_sql(),
            self.query.connection,
            self.query.id,
            self.user.id,
            1,
            settings.EXPLORER_DEFAULT_DOWNLOAD_ROWS,
            settings.EXPLORER_QUERY_TIMEOUT_MS,
        ).get()
        headers, data, _ = fetch_query_results(query_log_id)
        return self._get_output(headers, data, **kwargs)

    def _get_output(self, headers, data, **kwargs):
        """
        :param headers: list
        :param data: list
        :param kwargs: Optional. Any exporter-specific arguments.
        :return: File-like object
        """
        raise NotImplementedError

    def get_filename(self):
        # build list of valid chars, build filename from title and replace spaces
        valid_chars = '-_.() %s%s' % (string.ascii_letters, string.digits)
        filename = ''.join(c for c in self.query.title if c in valid_chars)
        filename = filename.replace(' ', '_')
        return '{}{}'.format(filename, self.file_extension)


class CSVExporter(BaseExporter):

    name = 'CSV'
    content_type = 'text/csv'
    file_extension = '.csv'

    def _get_output(self, headers, data, **kwargs):
        delim = kwargs.get('delim') or settings.EXPLORER_CSV_DELIMETER
        delim = '\t' if delim == 'tab' else str(delim)
        delim = settings.EXPLORER_CSV_DELIMETER if len(delim) > 1 else delim
        csv_data = StringIO()
        writer = csv.writer(csv_data, delimiter=delim)
        writer.writerow(headers)
        for row in data:
            writer.writerow(row)
        return csv_data


class JSONExporter(BaseExporter):

    name = 'JSON'
    content_type = 'application/json'
    file_extension = '.json'

    def _get_output(self, headers, data, **kwargs):
        rows = []
        for row in data:
            rows.append(  # pylint: disable=unnecessary-comprehension
                dict(
                    zip([str(h) if h is not None else '' for h in headers], row)
                )
            )

        json_data = json.dumps(rows, cls=DjangoJSONEncoder)
        return StringIO(json_data)


class ExcelExporter(BaseExporter):

    name = 'Excel'
    content_type = 'application/vnd.ms-excel'
    file_extension = '.xlsx'

    def _get_output(self, headers, data, **kwargs):
        import xlsxwriter  # pylint: disable=import-outside-toplevel

        output = BytesIO()

        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        ws = wb.add_worksheet(name=self._format_title())

        # Write headers
        row = 0
        col = 0
        header_style = wb.add_format({'bold': True})
        for header in headers:
            ws.write(row, col, str(header), header_style)
            col += 1

        # Write data
        row = 1
        col = 0
        for data_row in data:
            for data in data_row:
                # xlsxwriter can't handle timezone-aware datetimes or
                # UUIDs, so we help out here and just cast it to a
                # string
                if isinstance(data, (datetime, uuid.UUID)):
                    data = str(data)
                # JSON and Array fields
                if isinstance(data, (dict, list)):
                    data = json.dumps(data)
                ws.write(row, col, data)
                col += 1
            row += 1
            col = 0

        wb.close()
        return output

    def _format_title(self):
        # XLSX writer wont allow sheet names > 31 characters or that contain invalid characters
        # https://github.com/jmcnamara/XlsxWriter/blob/master/xlsxwriter/test/workbook/test_check_sheetname.py
        title = slugify(self.query.title)
        return title[:31]
