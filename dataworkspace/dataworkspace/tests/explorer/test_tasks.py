from datetime import datetime, timedelta

from django.test import TestCase

from dataworkspace.apps.explorer.models import QueryLog
from dataworkspace.apps.explorer.tasks import truncate_querylogs


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
