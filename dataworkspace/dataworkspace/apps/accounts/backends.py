import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from sentry_sdk import set_user

from dataworkspace.apps.applications.utils import create_user_from_sso

logger = logging.getLogger("app")


class AuthbrokerBackendUsernameIsEmail(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            email = request.META["HTTP_SSO_PROFILE_EMAIL"]
            contact_email = request.META["HTTP_SSO_PROFILE_CONTACT_EMAIL"]
            user_id = request.META["HTTP_SSO_PROFILE_USER_ID"]
            first_name = request.META["HTTP_SSO_PROFILE_FIRST_NAME"]
            last_name = request.META["HTTP_SSO_PROFILE_LAST_NAME"]
        except KeyError:
            return None

        primary_email = contact_email if contact_email else email
        user = create_user_from_sso(
            user_id,
            primary_email,
            first_name,
            last_name,
            "active",
            check_tools_access_if_user_exists=False,
        )
        set_user({"id": str(user.profile.sso_id), "email": user.email})

        if user.profile.first_login is None:
            user.profile.first_login = datetime.now()
            user.profile.save()

        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
