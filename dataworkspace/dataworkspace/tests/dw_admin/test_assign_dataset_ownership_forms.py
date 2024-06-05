from django.test import TestCase, RequestFactory
from dataworkspace.apps.dw_admin.views import (
    SelectUserForm,
    CurrentOwnerAndRoleForm,
)
from django.contrib.auth.models import User


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(obj):
        obj.user = User.objects.create(username="testuser", email="test@test.com")

    def setUp(self):
        self.factory = RequestFactory()


class SelectUserFormTest(BaseTest):
    def test_form_valid_data(self):
        form = SelectUserForm(data={"user": self.user.id})
        self.assertTrue(form.is_valid())

    def test_form_invalid_data(self):
        form = SelectUserForm(data={"user": None})
        self.assertFalse(form.is_valid())


class CurrentOwnerAndRoleFormTest(BaseTest):
    def test_form_valid_data(self):
        form = CurrentOwnerAndRoleForm(
            data={"user": self.user.id, "role": "information_asset_owner_id"}
        )
        self.assertTrue(form.is_valid())

    def test_form_invalid_user(self):
        form = CurrentOwnerAndRoleForm(data={"user": None, "role": "information_asset_owner_id"})
        self.assertFalse(form.is_valid())

    def test_form_invalid_role(self):
        form = CurrentOwnerAndRoleForm(data={"user": self.user.id, "role": None})
        self.assertFalse(form.is_valid())

    def test_form_invalid_data(self):
        form = CurrentOwnerAndRoleForm(data={"user": None, "role": None})
        self.assertFalse(form.is_valid())
