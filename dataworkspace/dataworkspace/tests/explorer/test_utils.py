import json
from datetime import date, datetime
from unittest.mock import call, MagicMock, Mock, patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

import pytest
import six
from waffle.testutils import override_flag

from dataworkspace.apps.explorer.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
)
from dataworkspace.apps.explorer.models import QueryLog
from dataworkspace.apps.explorer.utils import (
    execute_query_sync,
    get_total_pages,
    InvalidExplorerConnectionException,
)
from dataworkspace.tests.explorer.factories import SimpleQueryFactory
from dataworkspace.tests.factories import UserFactory
from dataworkspace.utils import DATA_EXPLORER_ASYNC_QUERIES_FLAG


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


class TestExecuteQuery:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.mock_cursor = MagicMock()  # pylint: disable=attribute-defined-outside-init
        # Mock the return value of SELECT COUNT(*) FROM ({query}) sq
        self.mock_cursor.fetchone.return_value.__getitem__.return_value = 1

        mock_connection = Mock()
        mock_connection.cursor.return_value = self.mock_cursor

        user_explorer_connection_patcher = patch(
            'dataworkspace.apps.explorer.utils.user_explorer_connection'
        )
        mock_user_explorer_connection = user_explorer_connection_patcher.start()

        mock_user_explorer_connection.return_value.__enter__.return_value = (
            mock_connection
        )

        self.user = UserFactory()
        self.request = MagicMock(user=self.user)
        yield
        user_explorer_connection_patcher.stop()

    @patch('dataworkspace.apps.explorer.utils.uuid')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_sync(self, mock_connection_settings, mock_uuid):
        mock_uuid.uuid4.return_value = '00000000-0000-0000-0000-000000000000'
        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query_sync(
            query.final_sql(), query.connection, query.id, self.user.id, 1, 100, 10000
        )
        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('DECLARE cur_0000000000 CURSOR WITH HOLD FOR select * from foo'),
            call('FETCH 100 FROM cur_0000000000'),
            call('CLOSE cur_0000000000'),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.uuid')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_sync_with_pagination(
        self, mock_connection_settings, mock_uuid
    ):
        mock_uuid.uuid4.return_value = '00000000-0000-0000-0000-000000000000'
        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query_sync(
            query.final_sql(), query.connection, query.id, self.user.id, 2, 100, 10000
        )

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('DECLARE cur_0000000000 CURSOR WITH HOLD FOR select * from foo'),
            call('MOVE 100 FROM cur_0000000000'),
            call("FETCH 100 FROM cur_0000000000"),
            call('CLOSE cur_0000000000'),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_sync_creates_query_log(self, mock_connection_settings):
        query = SimpleQueryFactory(sql='select * from foo', connection='conn')
        execute_query_sync(
            query.final_sql(), query.connection, query.id, self.user.id, 1, 100, 10000
        )
        log = QueryLog.objects.last()

        assert log.run_by_user == self.user
        assert log.query == query
        assert log.is_playground is False
        assert log.connection == query.connection
        assert log.duration is not None
        assert log.page == 1
        assert log.rows == 1
        assert log.state == QueryLog.STATE_COMPLETE

    def test_cant_query_with_unregistered_connection_sync(self):
        query = SimpleQueryFactory(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )
        with pytest.raises(InvalidExplorerConnectionException):
            execute_query_sync(
                query.final_sql(),
                query.connection,
                query.id,
                self.user.id,
                1,
                100,
                10000,
            )

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_csv_unicode_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        self.mock_cursor.description = [('a',), ('b',)]

        res = CSVExporter(request=self.request, query=SimpleQueryFactory()).get_output()
        assert res == 'a,b\r\n1,\r\nJenét,1\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_csv_custom_delimiter_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, 2)]
        self.mock_cursor.description = [('?column?',), ('?column?',)]

        res = CSVExporter(request=self.request, query=SimpleQueryFactory()).get_output(
            delim='|'
        )
        assert res == '?column?|?column?\r\n1|2\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_json_unicode_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        self.mock_cursor.description = [('a',), ('b',)]

        res = JSONExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res == json.dumps([{'a': 1, 'b': None}, {'a': 'Jenét', 'b': '1'}])

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_json_datetimes_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, date.today())]
        self.mock_cursor.description = [('a',), ('b',)]

        res = JSONExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res == json.dumps([{'a': 1, 'b': date.today()}], cls=DjangoJSONEncoder)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_excel_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', datetime.now())]

        res = ExcelExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res[:2] == six.b('PK')

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=False)
    def test_writing_excel_dict_fields_sync(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [
            (1, ['foo', 'bar']),
            (2, {'foo': 'bar'}),
        ]

        res = ExcelExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res[:2] == six.b('PK')
