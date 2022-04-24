from django.contrib.auth import get_user_model
from django.conf import settings

from django.core.exceptions import ImproperlyConfigured

ADMIN_EMAIL = "admin.user@example.com"


def create_or_update_user(username: str, email: str, first_name=None, last_name=None):
    if not settings.DEBUG:
        raise ImproperlyConfigured()

    users = get_user_model()
    user, created = users.objects.get_or_create(email=email, username=username)

    if first_name:
        user.first_name = first_name

    if last_name:
        user.last_name = last_name

    if first_name or last_name:
        user.save()

    password = users.objects.make_random_password(length=64)
    user.set_password(password)

    return user, created


def create_or_update_admin_user(username: str, email: str, stdout):
    admin, created = create_or_update_user(ADMIN_EMAIL, ADMIN_EMAIL, stdout)

    admin.is_superuser = True
    admin.is_staff = True
    admin.save()

    return admin, created
