import logging

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger('app')


class AuthbrokerBackendUsernameIsEmail(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            email = request.META['HTTP_SSO_PROFILE_EMAIL']
            user_id = request.META['HTTP_SSO_PROFILE_USER_ID']
            last_name = request.META['HTTP_SSO_PROFILE_LAST_NAME']
            first_name = request.META['HTTP_SSO_PROFILE_FIRST_NAME']
        except KeyError:
            if settings.DEBUG:
                email = 'bob.testerson@test.com' 
                user_id = 'aae8901a-082f-4f12-8c6c-fdf4aeba2d68' 
                last_name = 'Testerson' 
                first_name = 'Bob'
            else:
                return None

        # This allows a user to be created by email address before they
        # have logged in
        user, _ = get_user_model().objects.get_or_create(email=email)

        if not user.profile:
            user.save()

        changed = False
        if user.profile.sso_id != user_id:
            changed = True
            user.profile.sso_id = user_id

        if user.username != user.email:
            changed = True
            user.username = user.email

        if user.email != email:
            changed = True
            user.email = email

        if user.first_name != first_name:
            changed = True
            user.first_name = first_name

        if user.last_name != last_name:
            changed = True
            user.last_name = last_name

        if user.has_usable_password():
            changed = True
            user.set_unusable_password()

        if changed:
            user.save()

        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
