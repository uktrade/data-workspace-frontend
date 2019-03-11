from authbroker_client.backends import AuthbrokerBackend


class AuthbrokerBackendUsernameIsEmail(AuthbrokerBackend):

    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)
        if user is not None:
            user.username = user.email
            user.save()

        return user
