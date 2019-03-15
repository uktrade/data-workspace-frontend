from django.contrib.auth import (
    get_user_model,
)
from authbroker_client.client import (
    get_client,
    has_valid_token,
    get_profile,
)


class AuthbrokerBackend():
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

            return user

        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class AuthbrokerBackendUsernameIsEmail(AuthbrokerBackend):

    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)
        if user is not None:
            user.username = user.email
            user.save()

        return user
