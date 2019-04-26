from django.contrib.auth import (
    get_user_model,
)


class AuthbrokerBackendUsernameIsEmail():

    def authenticate(self, request, **kwargs):
        if request.META['REMOTE_ADDR'] != '127.0.0.1':
            return None

        try:
            email = request.META['HTTP_SSO_PROFILE_EMAIL']
            user_id = request.META['HTTP_SSO_PROFILE_USER_ID']
            last_name = request.META['HTTP_SSO_PROFILE_LAST_NAME']
            first_name  =  request.META['HTTP_SSO_PROFILE_FIRST_NAME']
        except KeyError:
            return None

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'first_name': first_name, 'last_name': last_name})

        # Ensure the user has a profile
        user.save()

        user.profile.sso_id = user_id
        user.username = user.email
        user.set_unusable_password()
        user.save()

        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
