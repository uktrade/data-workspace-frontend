import json
from datetime import date, datetime
from unittest.mock import call, MagicMock, patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

import pytest
import six

from dataworkspace.apps.explorer.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
)
from dataworkspace.apps.explorer.utils import cancel_query, get_total_pages
from dataworkspace.tests.explorer.factories import QueryLogFactory
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
                msg=f"Total rows {total_rows}, Page size {page_size}",
            )


class TestExporters:
    @pytest.fixture(autouse=True)
    def setUp(self):
        fetch_query_results_patcher = patch(
            "dataworkspace.apps.explorer.exporters.fetch_query_results"
        )
        mock_fetch_query_results = fetch_query_results_patcher.start()

        self.mock_fetch_query_results = mock_fetch_query_results

        self.user = UserFactory()
        self.request = MagicMock(user=self.user)
        yield
        fetch_query_results_patcher.stop()

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_csv_unicode_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("a", "b"),
            [(1, None), ("Jenét", 1)],
            None,
        )

        res = CSVExporter(request=self.request, querylog=QueryLogFactory()).get_output()
        assert res == "a,b\r\n1,\r\nJenét,1\r\n"

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_csv_custom_delimiter_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("?column?", "?column?"),
            [(1, 2)],
            None,
        )

        res = CSVExporter(request=self.request, querylog=QueryLogFactory()).get_output(delim="|")
        assert res == "?column?|?column?\r\n1|2\r\n"

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_json_unicode_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("a", "b"),
            [(1, None), ("Jenét", "1")],
            None,
        )

        res = JSONExporter(request=self.request, querylog=QueryLogFactory()).get_output()
        assert res == json.dumps([{"a": 1, "b": None}, {"a": "Jenét", "b": "1"}])

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_json_datetimes_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("a", "b"),
            [(1, date.today())],
            None,
        )

        res = JSONExporter(request=self.request, querylog=QueryLogFactory()).get_output()
        assert res == json.dumps([{"a": 1, "b": date.today()}], cls=DjangoJSONEncoder)

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_excel_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("a", "b"),
            [(1, None), ("Jenét", datetime.now())],
            None,
        )

        res = ExcelExporter(request=self.request, querylog=QueryLogFactory()).get_output()
        assert res[:2] == six.b("PK")

    @patch("dataworkspace.apps.explorer.utils.get_user_explorer_connection_settings")
    def test_writing_excel_dict_fields_sync(self, mock_connection_settings):
        self.mock_fetch_query_results.return_value = (
            ("a", "b"),
            [(1, ["foo", "bar"]), (2, {"foo": "bar"})],
            None,
        )

        res = ExcelExporter(request=self.request, querylog=QueryLogFactory()).get_output()
        assert res[:2] == six.b("PK")


class TestCancelQuery(TestCase):
    @patch("dataworkspace.apps.explorer.utils.connections")
    def test_cancel_query(self, mock_connections):
        queryLog = QueryLogFactory(sql="select '$$foo:bar$$', '$$qux$$';", pid=999)
        mock_cursor = mock_connections.__getitem__(
            queryLog.connection
        ).cursor.return_value.__enter__.return_value
        cancel_query(queryLog)

        expected_calls = [call("SELECT pg_cancel_backend(999)")]
        mock_cursor.execute.assert_has_calls(expected_calls)
