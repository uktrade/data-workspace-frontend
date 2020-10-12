from unittest.mock import call, Mock

import pytest
import six
from django.db import connections
from django.conf import settings

from dataworkspace.apps.explorer.models import (
    ColumnHeader,
    ColumnSummary,
    Query,
    QueryLog,
    QueryResult,
    SQLQuery,
)
from dataworkspace.tests.explorer.factories import SimpleQueryFactory
from dataworkspace.tests.factories import UserFactory


@pytest.mark.django_db(transaction=True)
class TestQueryModel:
    databases = ['default', 'my_database']

    def test_params_get_merged(self):
        q = SimpleQueryFactory(sql="select '$$foo$$';")
        q.params = {'foo': 'bar', 'mux': 'qux'}
        assert q.available_params() == {'foo': 'bar'}

    def test_default_params_used(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$';")
        assert q.available_params() == {'foo': 'bar'}

    def test_query_log(self):
        assert QueryLog.objects.count() == 0
        q = SimpleQueryFactory(connection='Alt')
        q.log(None)
        assert QueryLog.objects.count() == 1
        log = QueryLog.objects.first()

        assert log.run_by_user is None
        assert log.query == q
        assert log.is_playground is False
        assert log.connection == q.connection

    def test_query_logs_final_sql(self):
        q = SimpleQueryFactory(sql="select '$$foo$$';")
        q.params = {'foo': 'bar'}
        q.log(None)
        assert QueryLog.objects.count() == 1
        log = QueryLog.objects.first()

        assert log.sql == "select 'bar';"

    def test_playground_query_log(self):
        query = Query(sql='select 1;', title="Playground")
        query.log(None)
        log = QueryLog.objects.first()

        assert log.is_playground is True

    def test_get_run_count(self):
        q = SimpleQueryFactory()
        assert q.get_run_count() == 0
        expected = 4
        for _ in range(0, expected):
            q.log()
        assert q.get_run_count() == expected

    def test_avg_duration(self):
        q = SimpleQueryFactory()
        assert q.avg_duration() is None
        expected = 2.5
        ql = q.log()
        ql.duration = 2
        ql.save()
        ql = q.log()
        ql.duration = 3
        ql.save()
        assert q.avg_duration() == expected

    def test_log_saves_duration(self):
        user = UserFactory()
        q = SimpleQueryFactory()
        res, _ = q.execute_with_logging(user, None, 10, 10000)
        log = QueryLog.objects.first()

        assert log.duration == pytest.approx(res.duration, rel=1e-9)

    def test_final_sql_uses_merged_params(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$', '$$qux$$';")
        q.params = {'qux': 'mux'}
        expected = "select 'bar', 'mux';"

        assert q.final_sql() == expected

    def test_cant_query_with_unregistered_connection(self):
        from dataworkspace.apps.explorer.utils import (  # pylint: disable=import-outside-toplevel
            InvalidExplorerConnectionException,
        )

        user = UserFactory()
        q = SimpleQueryFactory.create(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )
        with pytest.raises(InvalidExplorerConnectionException):
            q.execute(user, None, 10, 10000)


@pytest.mark.django_db(transaction=True)
class TestQueryResults:
    connection_name = settings.EXPLORER_DEFAULT_CONNECTION
    databases = ['default', 'my_database']

    query = "select 1 as foo, 'qux' as mux;"

    @pytest.fixture(scope='function', autouse=True)
    def create_query_result(self):
        conn = connections[self.connection_name]
        self.qr = QueryResult(  # pylint: disable=attribute-defined-outside-init
            self.query, conn, 1, 1000, 10000
        )

    def test_column_access(self):
        self.qr._data = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        assert self.qr.column(1) == [2, 5, 8]

    def test_headers(self):
        assert str(self.qr.headers[0]) == "foo"
        assert str(self.qr.headers[1]) == "mux"

    def test_data(self):
        assert self.qr.data == [[1, "qux"]]

    def test_unicode_with_nulls(self):
        self.qr._headers = [ColumnHeader('num'), ColumnHeader('char')]
        self.qr._description = [("num",), ("char",)]
        self.qr._data = [[2, six.u("a")], [3, None]]
        self.qr.process()
        assert self.qr.data == [[2, "a"], [3, None]]

    def test_summary_gets_built(self):
        self.qr.process()
        assert len([h for h in self.qr.headers if h.summary]) == 1
        assert str(self.qr.headers[0].summary) == "foo"
        assert self.qr.headers[0].summary.stats["Sum"] == 1.0

    def test_summary_gets_built_for_multiple_cols(self):
        self.qr._headers = [ColumnHeader('a'), ColumnHeader('b')]
        self.qr._description = [("a",), ("b",)]
        self.qr._data = [[1, 10], [2, 20]]
        self.qr.process()
        assert len([h for h in self.qr.headers if h.summary]) == 2
        assert self.qr.headers[0].summary.stats["Sum"] == 3.0
        assert self.qr.headers[1].summary.stats["Sum"] == 30.0

    def test_numeric_detection(self):
        assert self.qr._get_numerics() == [0]

    def test_get_headers_no_results(self):
        self.qr._description = None
        assert [ColumnHeader('--')][0].title == self.qr._get_headers()[0].title


class TestColumnSummary:
    def test_executes(self):
        res = ColumnSummary('foo', [1, 2, 3])
        assert res.stats == {'Min': 1, 'Max': 3, 'Avg': 2, 'Sum': 6, 'NUL': 0}

    def test_handles_null_as_zero(self):
        res = ColumnSummary('foo', [1, None, 5])
        assert res.stats == {'Min': 0, 'Max': 5, 'Avg': 2, 'Sum': 6, 'NUL': 1}

    def test_empty_data(self):
        res = ColumnSummary('foo', [])
        assert res.stats == {'Min': 0, 'Max': 0, 'Avg': 0, 'Sum': 0, 'NUL': 0}


class TestSQLQuery:
    def test_connection_timeout(self):
        mock_cursor = Mock()
        mock_cursor.db.vendor = 'postgresql'
        mock_execute = Mock()
        mock_cursor.execute.side_effect = mock_execute

        query = SQLQuery(mock_cursor, "select * from foo", 100, 1, 10000)
        query._cursor_name = "test_cursor"
        query.execute()

        expected_calls = [
            call("SET statement_timeout = 10000"),
            call("DECLARE test_cursor CURSOR WITH HOLD FOR select * from foo"),
            call("FETCH 100 FROM test_cursor"),
        ]
        mock_execute.assert_has_calls(expected_calls)
