from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth.models import User
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.eventlog.models import EventLog


class YourBookmarksViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="testpassword")
        self.client.force_authenticate(user=self.user)

    def test_get_bookmarks(self):
        dataset = DataSet.objects.create(name="Test Dataset")
        EventLog.objects.create(
            user_has_bookmarked=self.user,
            event_type=EventLog.TYPE_DATASET_BOOKMARKED,
            content_object=dataset,
        )

        response = self.client.get(reverse("api-v2:recent_items:eventlog-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Test Dataset")

    def test_empty_bookmarks(self):
        response = self.client.get(reverse("api-v2:recent_items:eventlog-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
