import csv
import json
import re
import string
import uuid
from datetime import datetime
from io import BytesIO, StringIO
from numbers import Number

import waffle
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.module_loading import import_string
from django.utils.text import slugify

from dataworkspace.apps.explorer.utils import fetch_query_results


def get_exporter_class(format_):
    class_str = dict(settings.EXPLORER_DATA_EXPORTERS)[f"{format_}"]
    return import_string(class_str)


class BaseExporter:
    name = ""
    content_type = ""
    file_extension = ""

    def __init__(self, querylog, request):
        self.querylog = querylog
        self.request = request
        self.user = request.user

    @staticmethod
    def _escape_field(field):
        if not waffle.switch_is_active(settings.EXPLORER_CSV_INJECTION_PROTECTION_FLAG):
            return field
        # Allow numbers or numbers that are prefixed with . or -
        if isinstance(field, Number) or re.search(r"^([.\-]\d|-.\d|\d)", field):
            return field
        # Insert a ' as the first char if the string starts with =, +, - or @
        return re.sub(r"^([=+\-@])", r"'\1", field)

    def get_output(self, **kwargs):
        value = self.get_file_output(**kwargs).getvalue()
        return value

    def get_file_output(self, **kwargs):
        headers, data, _ = fetch_query_results(self.querylog.id)
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
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        filename = "".join(c for c in self.querylog.title if c in valid_chars)
        filename = filename.replace(" ", "_")
        return "{}{}".format(filename, self.file_extension)


class CSVExporter(BaseExporter):
    name = "CSV"
    content_type = "text/csv"
    file_extension = ".csv"

    def _get_output(self, headers, data, **kwargs):
        delim = kwargs.get("delim") or settings.EXPLORER_CSV_DELIMETER
        delim = "\t" if delim == "tab" else str(delim)
        delim = settings.EXPLORER_CSV_DELIMETER if len(delim) > 1 else delim
        csv_data = StringIO()
        writer = csv.writer(csv_data, delimiter=delim)
        writer.writerow(headers)
        for row in data:
            writer.writerow([self._escape_field(field) for field in row])
        return csv_data


class JSONExporter(BaseExporter):
    name = "JSON"
    content_type = "application/json"
    file_extension = ".json"

    def _get_output(self, headers, data, **kwargs):
        rows = []
        for row in data:
            rows.append(  # pylint: disable=unnecessary-comprehension
                dict(zip([str(h) if h is not None else "" for h in headers], row))
            )

        json_data = json.dumps(rows, cls=DjangoJSONEncoder)
        return StringIO(json_data)


class ExcelExporter(BaseExporter):
    name = "Excel"
    content_type = "application/vnd.ms-excel"
    file_extension = ".xlsx"

    def _get_output(self, headers, data, **kwargs):
        import xlsxwriter  # pylint: disable=import-outside-toplevel

        output = BytesIO()

        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        ws = wb.add_worksheet(name=self._format_title())

        # Write headers
        row = 0
        col = 0
        header_style = wb.add_format({"bold": True})
        for header in headers:
            ws.write(row, col, str(header), header_style)
            col += 1

        # Write data
        row = 1
        col = 0
        for data_rows in data:
            for data_row in data_rows:
                # xlsxwriter can't handle timezone-aware datetimes or
                # UUIDs, so we help out here and just cast it to a
                # string
                if isinstance(data_row, (datetime, uuid.UUID)):
                    data_row = str(data_row)
                # JSON and Array fields
                if isinstance(data_row, (dict, list)):
                    data_row = json.dumps(data_row)
                ws.write(row, col, self._escape_field(data_row))
                col += 1
            row += 1
            col = 0

        wb.close()
        return output

    def _format_title(self):
        # XLSX writer wont allow sheet names > 31 characters or that contain invalid characters
        # https://github.com/jmcnamara/XlsxWriter/blob/master/xlsxwriter/test/workbook/test_check_sheetname.py
        title = slugify(self.querylog.title)
        return title[:31]
