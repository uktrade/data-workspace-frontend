from unittest.mock import call, Mock

import six
from django.db import connections
from django.test import TestCase

from dataworkspace.apps.explorer.app_settings import EXPLORER_DEFAULT_CONNECTION as CONN
from dataworkspace.apps.explorer.models import (
    ColumnHeader,
    ColumnSummary,
    Query,
    QueryLog,
    QueryResult,
    SQLQuery,
)
from dataworkspace.tests.explorer.factories import SimpleQueryFactory


class TestQueryModel(TestCase):
    def test_params_get_merged(self):
        q = SimpleQueryFactory(sql="select '$$foo$$';")
        q.params = {'foo': 'bar', 'mux': 'qux'}
        self.assertEqual(q.available_params(), {'foo': 'bar'})

    def test_default_params_used(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$';")
        self.assertEqual(q.available_params(), {'foo': 'bar'})

    def test_query_log(self):
        self.assertEqual(0, QueryLog.objects.count())
        q = SimpleQueryFactory(connection='alt')
        q.log(None)
        self.assertEqual(1, QueryLog.objects.count())
        log = QueryLog.objects.first()
        self.assertEqual(log.run_by_user, None)
        self.assertEqual(log.query, q)
        self.assertFalse(log.is_playground)
        self.assertEqual(log.connection, q.connection)

    def test_query_logs_final_sql(self):
        q = SimpleQueryFactory(sql="select '$$foo$$';")
        q.params = {'foo': 'bar'}
        q.log(None)
        self.assertEqual(1, QueryLog.objects.count())
        log = QueryLog.objects.first()
        self.assertEqual(log.sql, "select 'bar';")

    def test_playground_query_log(self):
        query = Query(sql='select 1;', title="Playground")
        query.log(None)
        log = QueryLog.objects.first()
        self.assertTrue(log.is_playground)

    def test_get_run_count(self):
        q = SimpleQueryFactory()
        self.assertEqual(q.get_run_count(), 0)
        expected = 4
        for _ in range(0, expected):
            q.log()
        self.assertEqual(q.get_run_count(), expected)

    def test_avg_duration(self):
        q = SimpleQueryFactory()
        self.assertIsNone(q.avg_duration())
        expected = 2.5
        ql = q.log()
        ql.duration = 2
        ql.save()
        ql = q.log()
        ql.duration = 3
        ql.save()
        self.assertEqual(q.avg_duration(), expected)

    def test_log_saves_duration(self):
        q = SimpleQueryFactory()
        res, _ = q.execute_with_logging(None, None, 10, 10000)
        log = QueryLog.objects.first()

        self.assertAlmostEqual(log.duration, res.duration, places=9)

    def test_final_sql_uses_merged_params(self):
        q = SimpleQueryFactory(sql="select '$$foo:bar$$', '$$qux$$';")
        q.params = {'qux': 'mux'}
        expected = "select 'bar', 'mux';"
        self.assertEqual(q.final_sql(), expected)

    def test_cant_query_with_unregistered_connection(self):
        from dataworkspace.apps.explorer.utils import (  # pylint: disable=import-outside-toplevel
            InvalidExplorerConnectionException,
        )

        q = SimpleQueryFactory(
            sql="select '$$foo:bar$$', '$$qux$$';", connection='not_registered'
        )
        self.assertRaises(
            InvalidExplorerConnectionException, q.execute, None, 10, 10000
        )


class _AbstractQueryResults:
    connection_name = CONN
    query = "select 1 as foo, 'qux' as mux;"

    def setUp(self):
        conn = connections[self.connection_name]
        self.qr = QueryResult(self.query, conn, 1, 1000, 10000)

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


class TestQueryResults(_AbstractQueryResults, TestCase):
    databases = ['default']
    connection_name = CONN


class TestColumnSummary(TestCase):
    def test_executes(self):
        res = ColumnSummary('foo', [1, 2, 3])
        assert res.stats == {'Min': 1, 'Max': 3, 'Avg': 2, 'Sum': 6, 'NUL': 0}

    def test_handles_null_as_zero(self):
        res = ColumnSummary('foo', [1, None, 5])
        assert res.stats == {'Min': 0, 'Max': 5, 'Avg': 2, 'Sum': 6, 'NUL': 1}

    def test_empty_data(self):
        res = ColumnSummary('foo', [])
        assert res.stats == {'Min': 0, 'Max': 0, 'Avg': 0, 'Sum': 0, 'NUL': 0}


class TestSQLQuery(TestCase):
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
