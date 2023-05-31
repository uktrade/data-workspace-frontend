import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from dataworkspace.apps.core.models import get_user_model
from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    stable_identification_suffix,
)


class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    sso_id = models.UUIDField(unique=True, default=uuid.uuid4)
    tools_access_role_arn = models.TextField(default="", blank=True)

    # The access point ID is a combination of a root directory, POSIX user and group IDs under
    # which all requests come from: effectively overriding anything sent by the client
    home_directory_efs_access_point_id = models.CharField(unique=True, null=True, max_length=128)

    first_login = models.DateTimeField(null=True)

    class Meta:
        db_table = "app_profile"

    def get_private_schema(self):
        identification_suffix = stable_identification_suffix(str(self.sso_id), short=True)
        db_schema = f"{USER_SCHEMA_STEM}{identification_suffix}"

        return db_schema


@receiver(post_save, sender=get_user_model())
def save_user_profile(instance, **_):
    try:
        profile = instance.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=instance)
    profile.save()
