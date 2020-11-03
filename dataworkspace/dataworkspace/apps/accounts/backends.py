import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import publish_to_iam_role_creation_channel

logger = logging.getLogger('app')


class AuthbrokerBackendUsernameIsEmail(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            email = request.META['HTTP_SSO_PROFILE_EMAIL']
            contact_email = request.META['HTTP_SSO_PROFILE_CONTACT_EMAIL']
            related_emails = request.META['HTTP_SSO_PROFILE_RELATED_EMAILS'].split(',')
            user_id = request.META['HTTP_SSO_PROFILE_USER_ID']
            last_name = request.META['HTTP_SSO_PROFILE_LAST_NAME']
            first_name = request.META['HTTP_SSO_PROFILE_FIRST_NAME']
        except KeyError:
            return None

        # This allows a user to be created by email address before they
        # have logged in

        primary_email = contact_email if contact_email else email
        changed = False
        User = get_user_model()

        try:
            user = User.objects.get(profile__sso_id=user_id)
        except User.DoesNotExist:
            user, _ = User.objects.get_or_create(
                email__in=[email]
                + ([contact_email] if contact_email else [])
                + related_emails,
                defaults={'email': primary_email, 'username': primary_email},
            )

            # Save is required to create a profile object
            user.save()

            user.profile.sso_id = user_id
            try:
                user.save()
            except IntegrityError:
                # A concurrent request may have overtaken this one and created a user
                user = User.objects.get(profile__sso_id=user_id)

            if (
                user.user_permissions.filter(
                    codename='start_all_applications',
                    content_type=ContentType.objects.get_for_model(ApplicationInstance),
                ).exists()
                and not user.profile.tools_access_role_arn
            ):
                publish_to_iam_role_creation_channel(user)

        changed = False

        if user.username != primary_email:
            changed = True
            user.username = primary_email

        if user.email != primary_email:
            changed = True
            user.email = primary_email

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
