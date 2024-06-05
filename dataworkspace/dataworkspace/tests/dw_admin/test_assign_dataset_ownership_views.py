from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.template.response import TemplateResponse
from django.contrib.auth.models import User
from dataworkspace.apps.datasets.models import DataSet

from unittest.mock import patch, MagicMock

from dataworkspace.apps.dw_admin.views import (
    SelectUserAndRoleAdminView,
    SelectDatasetAndNewUserAdminView,
    ConfirmationAdminView,
)


class BaseTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(username="testuser", email="test@test.com")
        self.new_owner = User.objects.create(username="testnewowner", email="test@test.com")
        self.dummy_dataset = DataSet.objects.create(
            name="dummy dataset",
            slug="dummy-dataset",
            short_description="dummy dataset",
            description="dummy dataset",
        )


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

    def test_view_no_user_selected_reloads_page_with_error(self):
        request = self.factory.post(
            reverse("dw-admin:assign-dataset-ownership"),
            data={"user": "", "role": "information_asset_owner_id"},
        )
        request.user = self.user

        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertContains(response, "This field is required.", status_code=200)

    def test_view_no_role_selected_reloads_page_with_error(self):
        request = self.factory.post(
            reverse("dw-admin:assign-dataset-ownership"),
            data={"user": self.user.id, "role": ""},
        )
        request.user = self.user

        response = SelectUserAndRoleAdminView.as_view()(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertContains(response, "This field is required.", status_code=200)


class SelectDatasetAndNewUserAdminViewTest(BaseTest):
    @patch("dataworkspace.apps.dw_admin.views.SelectDatasetAndNewUserAdminView.get_context_data")
    def test_view_loads_page(self, mock_get_context_data):
        context = {
            "user_id": self.user,
            "role": "information_asset_owner",
            "datasets": [self.dummy_dataset],
        }
        mock_get_context_data.return_value = context

        request = self.factory.get(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(self.user.id, "information_asset_owner"),
            )
        )
        request.user = self.user

        response = SelectDatasetAndNewUserAdminView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data, context)

    @patch("dataworkspace.apps.dw_admin.views.SelectDatasetAndNewUserAdminView.get_context_data")
    def test_view_loads_alternative_message_if_no_datasets_found(self, mock_get_context_data):
        context = {
            "user_id": self.user,
            "role": "information_asset_owner",
            "datasets": None,
        }
        mock_get_context_data.return_value = context

        request = self.factory.get(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(self.user.id, "information_asset_owner"),
            )
        )
        request.user = self.user

        response = SelectDatasetAndNewUserAdminView.as_view()(request)
        response.render()

        self.assertEqual(response.context_data, context)
        self.assertContains(
            response,
            f"No datasets for {self.user} as information_asset_owner",
            status_code=200,
        )

    @patch("dataworkspace.apps.dw_admin.views.SelectDatasetAndNewUserAdminView.get_context_data")
    @patch("dataworkspace.apps.dw_admin.views.SelectUserForm")
    def test_view_no_datasets_selected_returns_page_with_error(
        self, mock_form, mock_get_context_data
    ):
        context = {
            "user_id": self.user,
            "role": "information_asset_owner",
            "datasets": [self.dummy_dataset],
        }
        mock_get_context_data.return_value = context

        form_instance = MagicMock()
        form_instance.is_valid.return_value = False
        form_instance.cleaned_data = {"dataset_ids": []}
        form_instance.add_error(None, "Select at least 1 dataset.")
        mock_form.return_value = form_instance

        request = self.factory.get(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(self.user.id, "information_asset_owner"),
            )
        )
        request.user = self.user

        response = SelectDatasetAndNewUserAdminView.as_view()(request)
        response.render()

        print(response.context_data)

        self.assertEqual(response.context_data, context)
        self.assertContains(
            response,
            "Select at least 1 dataset.",
            status_code=200,
        )


class ConfirmationAdminViewTest(BaseTest):
    def test_view(self):
        request = self.factory.get(reverse("dw-admin:assign-dataset-ownership-confirmation"))
        response = ConfirmationAdminView.as_view()(request)
        self.assertEqual(response.status_code, 200)
