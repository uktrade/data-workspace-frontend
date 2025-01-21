# from unittest import mock
# from django.test import TestCase, RequestFactory
# import pytest
# from dataworkspace.apps.maintenance.models import MaintenanceSettings
# from dataworkspace.apps.maintenance.maintenance import (
#     get_maintenance_settings,
#     maintenance_context,
#     update_maintenance_status,
#     MaintenanceMiddleware,
# )


# @pytest.mark.django_db
# class TestMaintenanceWithSetup(TestCase):
#     def setUp(self):
#         self.factory = RequestFactory()
#         self.patcher = mock.patch.object(MaintenanceSettings, "objects")
#         self.mock_objects = self.patcher.start()

#     def tearDown(self):
#         self.patcher.stop()

#     def test_get_maintenance_settings(
#         self,
#     ):
#         get_maintenance_settings()
#         self.mock_objects.first.assert_called_once()

#     def test_maintenance_context(self):
#         self.mock_objects.first.return_value = MaintenanceSettings(
#             maintenance_text="Test text", contact_email="test@gov.uk"
#         )
#         context = maintenance_context(self.factory.get("/"))
#         self.assertEqual(
#             context, {"maintenance_text": "Test text", "contact_email": "test@gov.uk"}
#         )

#     @mock.patch("dataworkspace.apps.maintenance.maintenance.set_maintenance_mode")
#     def test_update_maintenance_status(self, mock_set_maintenance_mode):
#         self.mock_objects.first.return_value = MaintenanceSettings(maintenance_toggle=True)
#         update_maintenance_status()
#         mock_set_maintenance_mode.assert_called_once_with(True)

#     @mock.patch("dataworkspace.apps.maintenance.maintenance.update_maintenance_status")
#     def test_maintenance_middleware(self, mock_update_maintenance_status):
#         middleware = MaintenanceMiddleware(lambda request: None)
#         middleware(self.factory.get("/"))
#         mock_update_maintenance_status.assert_called_once()


# @pytest.mark.django_db
# class TestMaintenanceWithoutSetup(TestCase):
#     def test_break_tags_are_not_stripped_from_maintenance_text(self):
#         MaintenanceSettings.objects.create(
#             maintenance_text="<br>Test text<br>",
#             maintenance_toggle=True,
#             contact_email="test@gov.uk",
#         )
#         updated_maintenance_settings = get_maintenance_settings()
#         self.assertHTMLEqual(updated_maintenance_settings.maintenance_text, "<br>Test text<br>")

#     def test_html_tags_are_stripped_from_maintenance_text(self):
#         MaintenanceSettings.objects.create(
#             maintenance_text="<p>Test text</p>",
#             maintenance_toggle=True,
#             contact_email="test@gov.uk",
#         )
#         updated_maintenance_settings = get_maintenance_settings()
#         self.assertHTMLEqual(updated_maintenance_settings.maintenance_text, "Test text")


# @pytest.mark.django_db
# class TestMaintenanceBaseSettings(TestCase):
#     def test_healthcheck_page_returns_ok_when_maintenance_mode_is_on(self):
#         MaintenanceSettings.objects.create(
#             maintenance_text="Test text", maintenance_toggle=True, contact_email="test@gov.uk"
#         )
#         response = self.client.get("/healthcheck")
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.content, b"OK")
