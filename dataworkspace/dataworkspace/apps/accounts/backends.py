import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from sentry_sdk import set_user

from dataworkspace.apps.applications.utils import get_sso_user

logger = logging.getLogger('app')


class AuthbrokerBackendUsernameIsEmail(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if (
            not request.path.startswith('/admin')
            and 'impersonated_user' in request.session
        ):
            return request.session['impersonated_user']
        user = get_sso_user(request)
        set_user({"id": str(user.profile.sso_id), "email": user.email})
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
