from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.template.response import TemplateResponse
from django.contrib.auth.models import User

from unittest.mock import patch

from dataworkspace.apps.dw_admin.views import (
    SelectUserAndRoleAdminView,
    SelectDatasetAndNewUserAdminView,
    ConfirmationAdminView,
)


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(obj):
        obj.user = User.objects.create(username="testuser", email="test@test.com")

    def setUp(self):
        self.factory = RequestFactory()


class SelectUserAndRoleAdminViewTest(BaseTest):
    def test_view_successful_redirect_on_valid_form_submission(self):
        request = self.factory.post(
            reverse("dw-admin:assign-dataset-ownership"),
            data={"user": self.user.id, "role": "information_asset_owner_id"},
        )
        request.user = self.user

        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(str(self.user.id), "information_asset_owner_id"),
            ),
        )

    def test_view_no_user_selected_reloads_page_with_error_listed(self):
        request = self.factory.post(
            reverse("dw-admin:assign-dataset-ownership"),
            data={"user": "", "role": "information_asset_owner_id"},
        )
        request.user = self.user

        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertContains(response, "This field is required.", status_code=200)

    def test_view_no_role_selected_reloads_page_with_error_listed(self):
        request = self.factory.post(
            reverse("dw-admin:assign-dataset-ownership"),
            data={"user": self.user.id, "role": ""},
        )
        request.user = self.user

        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertContains(response, "This field is required.", status_code=200)


class SelectDatasetAndNewUserAdminViewTest(BaseTest):
    @patch("dataworkspace.apps.dw_admin.views.SelectDatasetAndNewUserAdminView.get_datasets")
    @patch("dataworkspace.apps.dw_admin.views.SelectDatasetAndNewUserAdminView.get_context_data")
    def test_view(self, mock_get_datasets, mock_get_context_data):
        mock_get_datasets.return_value = ["1"]
        mock_get_context_data.return_value = {
            "user_id": self.user,
            "role": "information_asset_owner",
            "datasets": ["1"],
        }
        request = self.factory.get(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(self.user.id, "information_asset_owner"),
            )
        )
        response = SelectDatasetAndNewUserAdminView.as_view()(request)
        self.assertEqual(response.status_code, 200)


class ConfirmationAdminViewTest(BaseTest):
    def test_view(self):
        request = self.factory.get(reverse("dw-admin:assign-dataset-ownership-confirmation"))
        response = ConfirmationAdminView.as_view()(request)
        self.assertEqual(response.status_code, 200)
