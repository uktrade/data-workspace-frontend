import json
from datetime import date, datetime
from unittest.mock import call, MagicMock, Mock, patch

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

import pytest
import six


from dataworkspace.apps.explorer.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
)
from dataworkspace.apps.explorer.models import QueryLog
from dataworkspace.apps.explorer.utils import (
    execute_query,
    get_total_pages,
    InvalidExplorerConnectionException,
    QueryResult,
)
from dataworkspace.tests.explorer.factories import SimpleQueryFactory


class TestGetTotalPages(TestCase):
    def test_get_total_pages(self):
        tests = [
            (None, 10, 1),
            (10, None, 1),
            (80, 10, 8),
            (80, 5, 16),
            (81, 10, 9),
            (79, 10, 8),
        ]
        for total_rows, page_size, expected_total_pages in tests:
            actual_result = get_total_pages(total_rows, page_size)
            self.assertEqual(
                actual_result,
                expected_total_pages,
                msg=f'Total rows {total_rows}, Page size {page_size}',
            )


@pytest.mark.django_db(transaction=True)
class TestQueryResults:
    connection_name = settings.EXPLORER_DEFAULT_CONNECTION
    databases = ['default', 'my_database']

    query = "select 1 as foo, 'qux' as mux;"

    @pytest.fixture(scope='function', autouse=True)
    def create_query_result(self):
        self.qr = QueryResult(  # pylint: disable=attribute-defined-outside-init
            self.query, 1, 1000, 10000, None, None, None, None
        )

    def test_column_access(self):
        self.qr.data = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        assert self.qr.column(1) == [2, 5, 8]

    def test_unicode_with_nulls(self):
        self.qr.description = [("num",), ("char",)]
        self.qr.data = [[2, six.u("a")], [3, None]]
        assert self.qr.data == [[2, "a"], [3, None]]


class TestExecuteQuery:
    @pytest.fixture(scope='function', autouse=True)
    def create_mock_cursor(self):
        user_explorer_connection_patcher = patch(
            'dataworkspace.apps.explorer.utils.user_explorer_connection'
        )
        mock_user_explorer_connection = user_explorer_connection_patcher.start()

        self.mock_cursor = MagicMock()  # pylint: disable=attribute-defined-outside-init
        mock_connection = Mock()
        mock_connection.cursor.return_value = self.mock_cursor
        mock_user_explorer_connection.return_value.__enter__.return_value = (
            mock_connection
        )

        yield
        user_explorer_connection_patcher.stop()

    @patch('dataworkspace.apps.explorer.utils.uuid')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query(self, mock_connection_settings, mock_uuid):
        mock_uuid.uuid4.return_value = '00000000-0000-0000-0000-000000000000'

        query = SimpleQueryFactory(sql='select * from foo', connection='conn')

        execute_query(query, None, 1, 100, 10000, log_query=False)

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('DECLARE cur_0000000000 CURSOR WITH HOLD FOR select * from foo'),
            call('FETCH 100 FROM cur_0000000000'),
            call('CLOSE cur_0000000000'),
            call('select count(*) from (select * from foo) t'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.uuid')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_with_page(self, mock_connection_settings, mock_uuid):
        mock_uuid.uuid4.return_value = '00000000-0000-0000-0000-000000000000'

        query = SimpleQueryFactory(sql='select * from foo', connection='conn')

        execute_query(query, None, 2, 100, 10000, log_query=False)

        expected_calls = [
            call("SET statement_timeout = 10000"),
            call("DECLARE cur_0000000000 CURSOR WITH HOLD FOR select * from foo"),
            call('MOVE 100 FROM cur_0000000000'),
            call("FETCH 100 FROM cur_0000000000"),
            call('CLOSE cur_0000000000'),
            call('select count(*) from (select * from foo) t'),
        ]

        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_with_logging(self, mock_connection_settings):
        query = SimpleQueryFactory(sql='select * from foo', connection='conn')

        result = execute_query(query, None, 1, 100, 10000, log_query=True)
        assert QueryLog.objects.count() == 1
        log = QueryLog.objects.first()

        assert log.run_by_user is None
        assert log.query == query
        assert log.is_playground is False
        assert log.connection == query.connection
        assert log.duration == pytest.approx(result.duration, rel=1e-9)

    def test_cant_query_with_unregistered_connection(self):
        query = SimpleQueryFactory(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )

        with pytest.raises(InvalidExplorerConnectionException):
            execute_query(query, None, 1, 100, 10000, log_query=False)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_csv_unicode(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        self.mock_cursor.description = [('a',), ('b',)]

        res = CSVExporter(user=None, query=SimpleQueryFactory()).get_output()
        assert res == 'a,b\r\n1,\r\nJenét,1\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_csv_custom_delimiter(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, 2)]
        self.mock_cursor.description = [('?column?',), ('?column?',)]

        res = CSVExporter(user=None, query=SimpleQueryFactory()).get_output(delim='|')
        assert res == '?column?|?column?\r\n1|2\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_json_unicode(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        self.mock_cursor.description = [('a',), ('b',)]

        res = JSONExporter(user=None, query=SimpleQueryFactory()).get_output()
        assert res == json.dumps([{'a': 1, 'b': None}, {'a': 'Jenét', 'b': '1'}])

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_json_datetimes(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, date.today())]
        self.mock_cursor.description = [('a',), ('b',)]

        res = JSONExporter(user=None, query=SimpleQueryFactory()).get_output()
        assert res == json.dumps([{'a': 1, 'b': date.today()}], cls=DjangoJSONEncoder)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_excel(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', datetime.now())]

        res = ExcelExporter(user=None, query=SimpleQueryFactory()).get_output()
        assert res[:2] == six.b('PK')

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_excel_dict_fields(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [
            (1, ['foo', 'bar']),
            (2, {'foo': 'bar'}),
        ]

        res = ExcelExporter(user=None, query=SimpleQueryFactory()).get_output()
        assert res[:2] == six.b('PK')
