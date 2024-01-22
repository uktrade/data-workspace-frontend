from unittest import mock
from django.test import TestCase, RequestFactory
from dataworkspace.apps.maintenance.models import MaintenanceSettings
from dataworkspace.apps.maintenance.maintenance import (
    get_maintenance_settings,
    maintenance_context,
    update_maintenance_status,
    MaintenanceMiddleware,
)


class TestMaintenance(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.patcher = mock.patch.object(MaintenanceSettings, "objects")
        self.mock_objects = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_get_maintenance_settings(
        self,
    ):
        get_maintenance_settings()
        self.mock_objects.first.assert_called_once()

    def test_maintenance_context(self):
        self.mock_objects.first.return_value = MaintenanceSettings(maintenance_text="Test text")
        context = maintenance_context(self.factory.get("/"))
        self.assertEqual(context, {"maintenance_text": "Test text"})

    @mock.patch("dataworkspace.apps.maintenance.maintenance.set_maintenance_mode")
    def test_update_maintenance_status(self, mock_set_maintenance_mode):
        self.mock_objects.first.return_value = MaintenanceSettings(maintenance_toggle=True)
        update_maintenance_status()
        mock_set_maintenance_mode.assert_called_once_with(True)

    @mock.patch("dataworkspace.apps.maintenance.maintenance.update_maintenance_status")
    def test_maintenance_middleware(self, mock_update_maintenance_status):
        middleware = MaintenanceMiddleware(lambda request: None)
        middleware(self.factory.get("/"))
        mock_update_maintenance_status.assert_called_once()
