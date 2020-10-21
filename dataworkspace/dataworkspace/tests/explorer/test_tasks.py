from datetime import datetime, timedelta

from django.test import TestCase
from freezegun import freeze_time

from dataworkspace.apps.explorer.models import QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.tasks import (
    truncate_querylogs,
    cleanup_playground_sql_table,
)
from dataworkspace.tests.explorer.factories import PlaygroundSQLFactory


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
