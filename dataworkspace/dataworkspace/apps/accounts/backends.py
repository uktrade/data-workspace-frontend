import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db import IntegrityError

logger = logging.getLogger('app')


class AuthbrokerBackendUsernameIsEmail(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            email = request.META['HTTP_SSO_PROFILE_EMAIL']
            related_emails = request.META['HTTP_SSO_PROFILE_RELATED_EMAILS'].split(',')
            user_id = request.META['HTTP_SSO_PROFILE_USER_ID']
            last_name = request.META['HTTP_SSO_PROFILE_LAST_NAME']
            first_name = request.META['HTTP_SSO_PROFILE_FIRST_NAME']
        except KeyError:
            return None

        # This allows a user to be created by email address before they
        # have logged in

        changed = False
        User = get_user_model()

        try:
            user = User.objects.get(profile__sso_id=user_id)
        except User.DoesNotExist:
            user, _ = User.objects.get_or_create(
                email__in=[email] + related_emails,
                defaults={'email': email, 'username': email},
            )

            # Save is required to create a profile object
            user.save()

            user.profile.sso_id = user_id
            try:
                user.save()
            except IntegrityError:
                # A concurrent request may have overtaken this one and created a user
                user = User.objects.get(profile__sso_id=user_id)

        changed = False

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
