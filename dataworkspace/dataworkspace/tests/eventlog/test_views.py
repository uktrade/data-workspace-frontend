from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseAdminTestCase


class TestEventLogAdmin(BaseAdminTestCase):
    def test_event_log_csv_download(self):
        event1 = factories.EventLogFactory.create(
            user=self.user, related_object=factories.ReferenceDatasetFactory.create()
        )
        event2 = factories.EventLogFactory.create(
            related_object=factories.DatabaseFactory.create()
        )
        response = self._authenticated_post(
            reverse("admin:eventlog_eventlog_changelist"),
            {"action": "export_events", "_selected_action": [event1.id, event2.id]},
        )
        self.assertContains(response, '"timestamp","user","event_type","related_object","extra"')
        self.assertEqual(len(response.content.splitlines()), 3)
