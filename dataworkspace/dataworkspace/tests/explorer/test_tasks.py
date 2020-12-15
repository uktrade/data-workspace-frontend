from datetime import datetime, timedelta
from mock import call, Mock, MagicMock, patch

from django.test import TestCase
from freezegun import freeze_time

from dataworkspace.apps.explorer.models import QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.tasks import (
    truncate_querylogs,
    cleanup_playground_sql_table,
    cleanup_temporary_query_tables,
)
from dataworkspace.tests.explorer.factories import PlaygroundSQLFactory
from dataworkspace.tests.factories import UserFactory


class TestTasks(TestCase):
    def test_truncating_querylogs(self):
        QueryLog(sql='foo').save()
        QueryLog.objects.filter(sql='foo').update(
            run_at=datetime.now() - timedelta(days=30)
        )
        QueryLog(sql='bar').save()
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

    @patch('dataworkspace.apps.explorer.tasks.connections')
    def test_cleanup_temporary_query_tables(self, mock_connections):
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_cursor_ctx_manager = MagicMock()

        mock_cursor_ctx_manager.__enter__.return_value = mock_cursor
        mock_connection.cursor.return_value = mock_cursor_ctx_manager
        mock_connections.__getitem__.return_value = mock_connection

        user = UserFactory()
        user.profile.sso_id = '00000000-0000-0000-0000-000000000000'  # yields a short hexdigest of 12b9377c
        user.profile.save()

        # last run 1 day and 1 hour ago so its materialized view should be deleted
        with freeze_time(datetime.utcnow() - timedelta(days=1, hours=1)):
            query_log_1 = QueryLog.objects.create(run_by_user=user)

        # last run 2 hours ago so its materialized view should be kept
        with freeze_time(datetime.utcnow() - timedelta(hours=2)):
            QueryLog.objects.create(run_by_user=user)

        cleanup_temporary_query_tables()

        expected_calls = [
            call(
                f'DROP TABLE IF EXISTS _user_12b9377c._data_explorer_tmp_query_{query_log_1.id}'
            ),
        ]
        mock_cursor.execute.assert_has_calls(expected_calls)
