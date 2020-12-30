import json
from datetime import date, datetime, timedelta
from mock import call, Mock, MagicMock, patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from freezegun import freeze_time
import pytest
import six

from waffle.testutils import override_flag

from dataworkspace.apps.explorer.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
)
from dataworkspace.apps.explorer.models import PlaygroundSQL, QueryLog
from dataworkspace.apps.explorer.tasks import (
    truncate_querylogs,
    cleanup_playground_sql_table,
    cleanup_temporary_query_tables,
    execute_query_async,
)
from dataworkspace.apps.explorer.utils import InvalidExplorerConnectionException
from dataworkspace.tests.explorer.factories import (
    PlaygroundSQLFactory,
    QueryLogFactory,
    SimpleQueryFactory,
)
from dataworkspace.tests.factories import UserFactory
from dataworkspace.utils import DATA_EXPLORER_ASYNC_QUERIES_FLAG


class TestTasks(TestCase):
    def test_truncating_querylogs(self):
        QueryLogFactory(sql='foo')
        QueryLog.objects.filter(sql='foo').update(
            run_at=datetime.now() - timedelta(days=30)
        )
        QueryLogFactory(sql='bar')
        QueryLog.objects.filter(sql='bar').update(
            run_at=datetime.now() - timedelta(days=29)
        )
        truncate_querylogs(30)
        self.assertEqual(QueryLog.objects.count(), 1)

    def test_cleanup_playground_sql_table(self):
        PlaygroundSQLFactory.create()
        with freeze_time('2020-01-01T00:00:00.000000'):
            PlaygroundSQLFactory.create()

        cleanup_playground_sql_table()

        assert PlaygroundSQL.objects.count() == 1

    @patch('dataworkspace.apps.explorer.tasks.DATABASES_DATA')
    @patch('dataworkspace.apps.explorer.tasks.connections')
    def test_cleanup_temporary_query_tables(
        self, mock_connections, mock_databases_data
    ):
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_cursor_ctx_manager = MagicMock()

        mock_cursor_ctx_manager.__enter__.return_value = mock_cursor
        mock_connection.cursor.return_value = mock_cursor_ctx_manager
        mock_connections.__getitem__.return_value = mock_connection
        mock_databases_data.__getitem__.return_value = {
            "USER": "postgres",
            "NAME": "my_database" "",
        }

        user = UserFactory()
        user.profile.sso_id = '00000000-0000-0000-0000-000000000000'  # yields a short hexdigest of 12b9377c
        user.profile.save()

        # last run 1 day and 1 hour ago so its materialized view should be deleted
        with freeze_time(datetime.utcnow() - timedelta(days=1, hours=1)):
            query_log_1 = QueryLogFactory.create(run_by_user=user)

        # last run 2 hours ago so its materialized view should be kept
        with freeze_time(datetime.utcnow() - timedelta(hours=2)):
            QueryLogFactory.create(run_by_user=user)

        cleanup_temporary_query_tables()

        expected_calls = [
            call('GRANT USAGE ON SCHEMA _user_12b9377c TO postgres'),
            call(
                f'DROP TABLE IF EXISTS _user_12b9377c._data_explorer_tmp_query_{query_log_1.id}'
            ),
        ]
        mock_cursor.execute.assert_has_calls(expected_calls)


class TestExecuteQuery:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.mock_cursor = MagicMock()  # pylint: disable=attribute-defined-outside-init
        # Mock the return value of SELECT COUNT(*) FROM {query}
        self.mock_cursor.fetchone.return_value.__getitem__.return_value = 1

        mock_connection = Mock()
        mock_connection.cursor.return_value = self.mock_cursor

        user_explorer_connection_patcher = patch(
            'dataworkspace.apps.explorer.tasks.user_explorer_connection'
        )
        mock_user_explorer_connection = user_explorer_connection_patcher.start()

        mock_user_explorer_connection.return_value.__enter__.return_value = (
            mock_connection
        )

        self.user = UserFactory()
        self.request = MagicMock(user=self.user)
        yield
        user_explorer_connection_patcher.stop()

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    def test_execute_query_async(self, mock_connection_settings, mock_schema_suffix):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('foo', 23), ('bar', 25)]
        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query_async(
            query.final_sql(), query.connection, query.id, self.user.id, 1, 100, 10000
        )
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq LIMIT 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id} ("foo" integer, "bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    def test_execute_query_async_with_pagination(
        self, mock_connection_settings, mock_schema_suffix
    ):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('foo', 23), ('bar', 25)]
        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query_async(
            query.final_sql(), query.connection, query.id, self.user.id, 2, 100, 10000
        )
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq LIMIT 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id} ("foo" integer, "bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100 OFFSET 100'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    @patch('dataworkspace.apps.explorer.utils.db_role_schema_suffix_for_user')
    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    def test_execute_query_async_with_duplicated_column_names(
        self, mock_connection_settings, mock_schema_suffix
    ):
        mock_schema_suffix.return_value = '12b9377c'
        # See utils.TYPE_CODES_REVERSED for data type codes returned in cursor description
        self.mock_cursor.description = [('bar', 23), ('bar', 25)]
        query = SimpleQueryFactory(sql='select * from foo', connection='conn', id=1)

        execute_query_async(
            query.final_sql(), query.connection, query.id, self.user.id, 1, 100, 10000
        )
        query_log_id = QueryLog.objects.first().id

        expected_calls = [
            call('SET statement_timeout = 10000'),
            call('SELECT * FROM (select * from foo) sq LIMIT 0'),
            call(
                f'CREATE TABLE _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' ("col_1_bar" integer, "col_2_bar" text)'
            ),
            call(
                f'INSERT INTO _user_12b9377c._data_explorer_tmp_query_{query_log_id}'
                ' SELECT * FROM (select * from foo) sq LIMIT 100'
            ),
            call('SELECT COUNT(*) FROM (select * from foo) sq'),
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls)

    def test_cant_query_with_unregistered_connection_async(self):
        query = SimpleQueryFactory(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )
        with pytest.raises(InvalidExplorerConnectionException):
            execute_query_async(
                query.final_sql(),
                query.connection,
                query.id,
                self.user.id,
                1,
                100,
                10000,
            )

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_csv_unicode_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (
            ['a', 'b'],
            [[1, None], [u'Jen\xe9t', '1']],
            None,
        )

        res = CSVExporter(request=self.request, query=SimpleQueryFactory()).get_output()
        assert res == 'a,b\r\n1,\r\nJenét,1\r\n'

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_csv_custom_delimiter_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (
            ['?column?', '?column?'],
            [[1, 2]],
            None,
        )

        res = CSVExporter(request=self.request, query=SimpleQueryFactory()).get_output(
            delim='|'
        )
        assert res == '?column?|?column?\r\n1|2\r\n'

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_json_unicode_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (
            ['a', 'b'],
            [[1, None], [u'Jen\xe9t', '1']],
            None,
        )

        res = JSONExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res == json.dumps([{'a': 1, 'b': None}, {'a': 'Jenét', 'b': '1'}])

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_json_datetimes_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (['a', 'b'], [[1, date.today()]], None)

        res = JSONExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res == json.dumps([{'a': 1, 'b': date.today()}], cls=DjangoJSONEncoder)

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_excel_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (
            ['a', 'b'],
            [[1, None], [u'Jenét', datetime.now()]],
            None,
        )

        res = ExcelExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res[:2] == six.b('PK')

    @patch('dataworkspace.apps.explorer.tasks.get_user_explorer_connection_settings')
    @patch('dataworkspace.apps.explorer.exporters.fetch_query_results')
    @override_flag(DATA_EXPLORER_ASYNC_QUERIES_FLAG, active=True)
    def test_writing_excel_dict_fields_async(
        self, mock_fetch_query_results, mock_connection_settings
    ):
        # Mock the field names returned by SELECT * FROM ({query}) sq LIMIT 0
        self.mock_cursor.description = [(None, 23)]
        mock_fetch_query_results.return_value = (
            ['a', 'b'],
            [[1, ['foo', 'bar']], [2, {'foo': 'bar'}]],
            None,
        )

        res = ExcelExporter(
            request=self.request, query=SimpleQueryFactory()
        ).get_output()
        assert res[:2] == six.b('PK')
