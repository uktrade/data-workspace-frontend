import tempfile
from collections import defaultdict
from datetime import date
from wsgiref.util import FileWrapper
from zipfile import ZipFile

from django.http import HttpResponse

from dataworkspace.apps.explorer.exporters import CSVExporter


def generate_report_action(description="Generate CSV file from SQL query"):
    def generate_report(modeladmin, request, queryset):
        queries = (len(queryset) > 0 and _package(queryset)) or defaultdict(int)
        response = HttpResponse(queries["data"], content_type=queries["content_type"])
        response['Content-Disposition'] = queries["filename"]
        response['Content-Length'] = queries["length"]
        return response

    generate_report.short_description = description
    return generate_report


def _package(queries):
    ret = {}
    is_one = len(queries) == 1
    ret["content_type"] = (is_one and 'text/csv') or 'application/zip'
    ret["filename"] = (
        is_one and _name_root('%s.csv' % queries[0].title.replace(',', ''))
    ) or _name_root("Report_%s.zip" % date.today())
    ret["data"] = (is_one and CSVExporter(queries[0]).get_output()) or _build_zip(
        queries
    )
    ret["length"] = is_one and len(ret["data"]) or ret["data"].blksize
    return ret


def _name_root(filename):
    return f'attachment; filename={filename}'


def _build_zip(queries):
    temp = tempfile.TemporaryFile()
    zip_file = ZipFile(temp, 'w')
    for r in queries:
        zip_file.writestr('%s.csv' % r.title, CSVExporter(r).get_output() or "Error!")
    zip_file.close()
    ret = FileWrapper(temp)
    temp.seek(0)
    return ret
