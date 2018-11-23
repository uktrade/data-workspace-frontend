from authbroker_client.backends import AuthbrokerBackend


class AuthbrokerBackendAllSuperuser(AuthbrokerBackend):
    # All users that manage to "authenticate" by the broker are also authorized
    # to be superuser

    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)
        if user is not None:
            user.username = user.email
            user.is_staff = True
            user.is_superuser = True
            user.save()

        return user
