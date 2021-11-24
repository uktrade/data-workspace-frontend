from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseAdminTestCase


class TestDatasetFinderQueryLogAdmin(BaseAdminTestCase):
    def test_event_log_csv_download(self):
        factories.DatasetFinderQueryLogFactory.create(query="something")
        response = self._authenticated_get(
            reverse("admin:finder_datasetfinderquerylog_changelist"),
        )
        self.assertContains(response, "something")
