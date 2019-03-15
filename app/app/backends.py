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
        if has_valid_token(client):
            User = get_user_model()

            profile = get_profile(client)

            user, created = User.objects.get_or_create(
                email=profile['email'],
                defaults={'first_name': profile['first_name'], 'last_name': profile['last_name']})

            if created:
                user.set_unusable_password()

            user.username = user.email
            user.save()

            return user

        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None