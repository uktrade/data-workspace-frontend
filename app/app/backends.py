from django.contrib.auth import (
    get_user_model,
)
from authbroker_client.client import (
    get_client,
    has_valid_token,
    get_profile,
)


class AuthbrokerBackendUsernameIsEmail():

    def authenticate(self, request, **kwargs):
        client = get_client(request)

        if not has_valid_token(client):
            return None

        User = get_user_model()

        profile = get_profile(client)

        user, created = User.objects.get_or_create(
            email=profile['email'],
            defaults={'first_name': profile['first_name'], 'last_name': profile['last_name']})

        user.profile.sso_id = profile['user_id']
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