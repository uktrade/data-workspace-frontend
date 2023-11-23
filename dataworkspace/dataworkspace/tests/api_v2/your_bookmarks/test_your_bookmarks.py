from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.eventlog.models import EventLog


class YourBookmarksViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="testpassword")
        self.client.force_authenticate(user=self.user)

    def test_get_bookmarks(self):
        # Create a DataSet with bookmark for the user
        dataset = DataSet.objects.create(name="Test Dataset")
        EventLog.objects.create(
            user_has_bookmarked=self.user,
            event_type=EventLog.TYPE_DATASET_BOOKMARKED,
            content_object=dataset,
        )

        # Make a GET request to the viewset
        response = self.client.get("/your-bookmarks-endpoint/")

        # Check that the response has a 200 status code
        self.assertEqual(response.status_code, 200)

        # Check that the serialized data in the response matches your expectations
        self.assertEqual(response.data["results"][0]["name"], "Test Dataset")

    def test_empty_bookmarks(self):
        # Make a GET request to the viewset
        response = self.client.get("/your-bookmarks-endpoint/")

        # Check that the response has a 200 status code
        self.assertEqual(response.status_code, 200)

        # Check that the response contains an empty list of results
        self.assertEqual(response.data["results"], [])

    # You can add more test cases for other actions (create, update, delete) if needed
