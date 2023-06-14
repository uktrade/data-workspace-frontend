import uuid

import pytest
from mock import mock
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.test.client import RequestFactory
from dataworkspace.apps.accounts.backends import AuthbrokerBackendUsernameIsEmail
from dataworkspace.apps.applications.utils import create_user_from_sso
from dataworkspace.tests import factories


class TestAuthbrokerBackend:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.accounts.backends.set_user")
    def test_create_user_from_sso(self, _):
        broker = AuthbrokerBackendUsernameIsEmail()
        request = RequestFactory()
        request.META = {
            "HTTP_SSO_PROFILE_EMAIL": "user1@email1.com",
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": "user1@email2.com",
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "user1@email3.com,user1@email4.com",
            "HTTP_SSO_PROFILE_USER_ID": uuid.uuid4(),
            "HTTP_SSO_PROFILE_FIRST_NAME": "Bob",
            "HTTP_SSO_PROFILE_LAST_NAME": "Testeroni",
        }
        user = broker.authenticate(request)
        assert user.username == request.META["HTTP_SSO_PROFILE_USER_ID"]
        assert user.email == request.META["HTTP_SSO_PROFILE_CONTACT_EMAIL"]
        assert user.profile.sso_id == request.META["HTTP_SSO_PROFILE_USER_ID"]
        assert user.profile.sso_status == "active"

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.accounts.backends.set_user")
    def test_sso_user_email_change(self, _):
        user = factories.UserFactory(
            username="initial@email.com",
            email="initial@email.com",
        )
        broker = AuthbrokerBackendUsernameIsEmail()
        request = RequestFactory()
        request.META = {
            "HTTP_SSO_PROFILE_EMAIL": "updated@email.com",
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": "updated-contact@email.com",
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "user1@email3.com,user1@email4.com",
            "HTTP_SSO_PROFILE_USER_ID": user.profile.sso_id,
            "HTTP_SSO_PROFILE_FIRST_NAME": "Bob",
            "HTTP_SSO_PROFILE_LAST_NAME": "Testeroni",
        }
        broker.authenticate(request)
        user.refresh_from_db()
        assert user.username == str(request.META["HTTP_SSO_PROFILE_USER_ID"])
        assert user.email == request.META["HTTP_SSO_PROFILE_CONTACT_EMAIL"]
        assert user.profile.sso_id == request.META["HTTP_SSO_PROFILE_USER_ID"]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.accounts.backends.set_user")
    def test_user_with_email_already_exists(self, _):
        existing_user = factories.UserFactory(
            username="exists@email.com",
            email="exists@email.com",
        )
        broker = AuthbrokerBackendUsernameIsEmail()
        request = RequestFactory()
        request.META = {
            "HTTP_SSO_PROFILE_EMAIL": "exists@email.com",
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": "exists@email.com",
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
            "HTTP_SSO_PROFILE_USER_ID": "67ad2d11-464c-4c5f-8838-5dd8087ca426",
            "HTTP_SSO_PROFILE_FIRST_NAME": "Bob",
            "HTTP_SSO_PROFILE_LAST_NAME": "Testeroni",
        }
        logged_in_user = broker.authenticate(request)
        existing_user.refresh_from_db()
        assert logged_in_user.is_authenticated
        assert existing_user.username != logged_in_user.username
        assert existing_user.email == logged_in_user.email
        assert existing_user.profile.sso_id != logged_in_user.profile.sso_id
        assert get_user_model().objects.filter(email="exists@email.com").count() == 2

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.accounts.backends.set_user")
    def test_user_with_multiple_sso_accounts(self, _):
        user1 = factories.UserFactory(
            username="user1",
            email="user1@test.com",
        )
        broker = AuthbrokerBackendUsernameIsEmail()
        request = RequestFactory()
        request.META = {
            "HTTP_SSO_PROFILE_EMAIL": user1.email,
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": user1.email,
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
            "HTTP_SSO_PROFILE_USER_ID": "ea4e3756-5102-46ef-9025-b89b245f1084",
            "HTTP_SSO_PROFILE_FIRST_NAME": "Bob",
            "HTTP_SSO_PROFILE_LAST_NAME": "Testeroni",
        }
        authed_user = broker.authenticate(request)
        # If the logging in user already has an account with a different
        # SSO ID we should create a new account for them
        assert authed_user.id != user1.id
        assert authed_user.username == "ea4e3756-5102-46ef-9025-b89b245f1084"
        assert authed_user.email == user1.email
        assert authed_user.profile.sso_id == "ea4e3756-5102-46ef-9025-b89b245f1084"


class TestCreateUserFromSSO:
    @pytest.mark.django_db
    def test_user_exists_with_different_sso_id(self):
        existing_user = factories.UserFactory.create()
        try:
            new_user = create_user_from_sso(
                uuid.uuid4(),
                existing_user.email,
                "Bob",
                "Bobson",
                "active",
                check_tools_access_if_user_exists=False,
            )
        except IntegrityError as e:
            raise AssertionError(f"Duplicate user {e}") from e
        assert existing_user.id != new_user.id
