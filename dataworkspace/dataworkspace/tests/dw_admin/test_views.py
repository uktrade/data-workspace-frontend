from django.test import TestCase, RequestFactory
from django.urls import reverse
from mock import patch
from dataworkspace.apps.dw_admin.views import (
    SelectUserForm,
    CurrentOwnerAndRoleForm,
    SelectUserAndRoleAdminView,
    SelectDatasetAndNewUserAdminView,
    ConfirmationAdminView,
)
from django.contrib.auth.models import User


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(obj):
        obj.user = User.objects.create(username="testuser", email="test@test.com")

    def setUp(self):
        self.factory = RequestFactory()


class SelectUserFormTest(BaseTest):
    def test_form(self):
        form = SelectUserForm(data={"user": 1})
        self.assertTrue(form.is_valid())


class CurrentOwnerAndRoleFormTest(BaseTest):
    def test_form(self):
        form = CurrentOwnerAndRoleForm(
            data={"user": self.user.id, "role": "information_asset_owner_id"}
        )
        self.assertTrue(form.is_valid())


class SelectUserAndRoleAdminViewTest(BaseTest):
    def test_view(self):
        request = self.factory.get(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(
                    "1",
                    "information_asset_owner_id",
                ),
            )
        )
        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertEqual(response.status_code, 200)


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
