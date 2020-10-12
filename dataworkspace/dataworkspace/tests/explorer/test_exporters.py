import json

from datetime import date, datetime

import pytest
from six import b

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections
from django.utils import timezone

from dataworkspace.apps.explorer.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
)
from dataworkspace.apps.explorer.models import QueryResult
from dataworkspace.tests.explorer.factories import SimpleQueryFactory
from dataworkspace.tests.factories import UserFactory


@pytest.mark.django_db(transaction=True)
class TestCsv:
    def test_writing_unicode(self):
        res = QueryResult(
            SimpleQueryFactory(sql='select 1 as "a", 2 as "b"').sql,
            connections[settings.EXPLORER_DEFAULT_CONNECTION],
            1,
            1000,
            10000,
        )
        res.execute_query()
        res.process()
        res._data = [[1, None], [u"Jenét", '1']]

        res = CSVExporter(user=None, query=None)._get_output(res).getvalue()
        assert res == 'a,b\r\n1,\r\nJenét,1\r\n'

    def test_custom_delimiter(self):
        user = UserFactory()
        q = SimpleQueryFactory(sql='select 1, 2')
        exporter = CSVExporter(user=user, query=q)
        res = exporter.get_output(delim='|')
        assert res == '?column?|?column?\r\n1|2\r\n'


@pytest.mark.django_db(transaction=True)
class TestJson:
    def test_writing_json(self):
        res = QueryResult(
            SimpleQueryFactory(sql='select 1 as "a", 2 as "b"').sql,
            connections[settings.EXPLORER_DEFAULT_CONNECTION],
            1,
            1000,
            10000,
        )
        res.execute_query()
        res.process()
        res._data = [[1, None], [u"Jenét", '1']]

        res = JSONExporter(user=None, query=None)._get_output(res).getvalue()
        expected = [{'a': 1, 'b': None}, {'a': 'Jenét', 'b': '1'}]
        assert res == json.dumps(expected)

    def test_writing_datetimes(self):
        res = QueryResult(
            SimpleQueryFactory(sql='select 1 as "a", 2 as "b"').sql,
            connections[settings.EXPLORER_DEFAULT_CONNECTION],
            1,
            1000,
            10000,
        )
        res.execute_query()
        res.process()
        res._data = [[1, date.today()]]

        res = JSONExporter(user=None, query=None)._get_output(res).getvalue()
        expected = [{'a': 1, 'b': date.today()}]
        assert res == json.dumps(expected, cls=DjangoJSONEncoder)


@pytest.mark.django_db(transaction=True)
class TestExcel:
    def test_writing_excel(self):
        """ This is a pretty crap test. It at least exercises the code.
            If anyone wants to go through the brain damage of actually building
            an 'expected' xlsx output and comparing it see
            https://github.com/jmcnamara/XlsxWriter/blob/master/xlsxwriter/test/helperfunctions.py
            for reference by all means submit a pull request!
        """
        res = QueryResult(
            SimpleQueryFactory(
                sql='select 1 as "a", 2',
                title='\\/*[]:?this title is longer than 32 characters',
            ).sql,
            connections[settings.EXPLORER_DEFAULT_CONNECTION],
            1,
            1000,
            10000,
        )
        res.execute_query()
        res.process()

        d = datetime.now()
        d = timezone.make_aware(d, timezone.get_current_timezone())

        res._data = [[1, None], [u"Jenét", d]]

        res = (
            ExcelExporter(user=None, query=SimpleQueryFactory())
            ._get_output(res)
            .getvalue()
        )

        expected = b('PK')

        assert res[:2] == expected

    def test_writing_dict_fields(self):
        res = QueryResult(
            SimpleQueryFactory(
                sql='select 1 as "a", 2',
                title='\\/*[]:?this title is longer than 32 characters',
            ).sql,
            connections[settings.EXPLORER_DEFAULT_CONNECTION],
            1,
            1000,
            10000,
        )

        res.execute_query()
        res.process()

        res._data = [[1, ['foo', 'bar']], [2, {'foo': 'bar'}]]

        res = (
            ExcelExporter(user=None, query=SimpleQueryFactory())
            ._get_output(res)
            .getvalue()
        )

        expected = b('PK')

        assert res[:2] == expected
