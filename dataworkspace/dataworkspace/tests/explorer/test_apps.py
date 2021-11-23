from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from dataworkspace.apps.explorer.apps import _validate_connections


class TestApps(TestCase):
    @patch("dataworkspace.apps.explorer.apps._get_default")
    def test_validates_default_connections(self, mocked_connection):
        mocked_connection.return_value = "garbage"
        self.assertRaises(ImproperlyConfigured, _validate_connections)

    @patch("dataworkspace.apps.explorer.apps._get_explorer_connections")
    def test_validates_all_connections(self, mocked_connections):
        mocked_connections.return_value = {"garbage1": "in", "garbage2": "out"}
        self.assertRaises(ImproperlyConfigured, _validate_connections)
