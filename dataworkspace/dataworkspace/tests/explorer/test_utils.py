import json
from datetime import date, datetime
from unittest.mock import call, MagicMock, Mock, patch

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
from dataworkspace.tests.factories import UserFactory


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
    query = "select 1 as foo, 'qux' as mux;"

    @pytest.fixture(scope='function', autouse=True)
    def create_query_result(self):
        self.qr = QueryResult(  # pylint: disable=attribute-defined-outside-init
            self.query, 1, 1000, 10000, None, None, None, None, None
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
    def setUp(self):
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
        self.user = UserFactory()
        yield
        user_explorer_connection_patcher.stop()
        self.user.delete()

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query(self, mock_connection_settings, mock_schema_suffix):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('foo', 23), ('bar', 25)]

        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query(query, self.user, 1, 100, 10000)
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq limit 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id} ("foo" integer, "bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100'
            ),
            call(
                f'SELECT * FROM _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_with_pagination(
        self, mock_connection_settings, mock_schema_suffix
    ):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('foo', 23), ('bar', 25)]

        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query(query, self.user, 2, 100, 10000)
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq limit 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id} ("foo" integer, "bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100 OFFSET 100'
            ),
            call(
                f'SELECT * FROM _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_with_duplicated_column_names(
        self, mock_connection_settings, mock_schema_suffix
    ):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('bar', 23), ('bar', 25)]

        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query(query, self.user, 2, 100, 10000)
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq limit 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' ("col_1_bar" integer, "col_2_bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100 OFFSET 100'
            ),
            call(
                f'SELECT * FROM _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_execute_query_creates_query_log(self, mock_connection_settings):
        query = SimpleQueryFactory(sql='select * from foo', connection='conn')
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('foo', 23), ('bar', 23)]

        result = execute_query(query, self.user, 1, 100, 10000)
        assert QueryLog.objects.count() == 1
        log = QueryLog.objects.first()

        assert log.run_by_user == self.user
        assert log.query == query
        assert log.is_playground is False
        assert log.connection == query.connection
        assert log.duration == pytest.approx(result.duration, rel=1e-9)

    def test_cant_query_with_unregistered_connection(self):
        query = SimpleQueryFactory(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )

        with pytest.raises(InvalidExplorerConnectionException):
            execute_query(query, self.user, 1, 100, 10000)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_csv_unicode(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('a', 23), ('b', 23)]

        res = CSVExporter(user=self.user, query=SimpleQueryFactory()).get_output()
        assert res == 'a,b\r\n1,\r\nJenét,1\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_csv_custom_delimiter(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, 2)]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('?column?', 23), ('?column?', 23)]

        res = CSVExporter(user=self.user, query=SimpleQueryFactory()).get_output(
            delim='|'
        )
        assert res == '?column?|?column?\r\n1|2\r\n'

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_json_unicode(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', '1')]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('a', 23), ('b', 23)]

        res = JSONExporter(user=self.user, query=SimpleQueryFactory()).get_output()
        assert res == json.dumps([{'a': 1, 'b': None}, {'a': 'Jenét', 'b': '1'}])

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_json_datetimes(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, date.today())]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('a', 23), ('b', 23)]

        res = JSONExporter(user=self.user, query=SimpleQueryFactory()).get_output()
        assert res == json.dumps([{'a': 1, 'b': date.today()}], cls=DjangoJSONEncoder)

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_excel(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [(1, None), (u'Jenét', datetime.now())]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('a', 23), ('b', 23)]

        res = ExcelExporter(user=self.user, query=SimpleQueryFactory()).get_output()
        assert res[:2] == six.b('PK')

    @patch('dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings')
    def test_writing_excel_dict_fields(self, mock_connection_settings):
        self.mock_cursor.__iter__.return_value = [
            (1, ['foo', 'bar']),
            (2, {'foo': 'bar'}),
        ]
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description.
        # As this test makes no assertions on the cursor execute statement, this value can
        # be anything in the TYPE_CODES_REVERSED dict
        self.mock_cursor.description = [('a', 23), ('b', 23)]

        res = ExcelExporter(user=self.user, query=SimpleQueryFactory()).get_output()
        assert res[:2] == six.b('PK')
