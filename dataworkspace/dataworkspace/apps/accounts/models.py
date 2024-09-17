import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from dataworkspace.apps.core.utils import USER_SCHEMA_STEM, stable_identification_suffix
from dataworkspace.apps.core.models import TimeStampedModel
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event


class HomePageProfile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.PROTECT)
    bookmarks = models.BooleanField(default=True)
    recent_collections = models.BooleanField(default=True)
    recent_items = models.BooleanField(default=True)
    recent_tools = models.BooleanField(default=True)

    class Meta:
        db_table = "app_homepage_profile"


class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    sso_id = models.UUIDField(unique=True, default=uuid.uuid4)
    tools_access_role_arn = models.TextField(default="", blank=True)
    sso_status = models.CharField(
        max_length=256, choices=(("active", "Active"), ("inactive", "Inactive")), default="active"
    )
    # The access point ID is a combination of a root directory, POSIX user and group IDs under
    # which all requests come from: effectively overriding anything sent by the client
    home_directory_efs_access_point_id = models.CharField(unique=True, null=True, max_length=128)

    first_login = models.DateTimeField(null=True)

    tools_certification_date = models.DateField(null=True, blank=True)

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


class UserDataTableView(TimeStampedModel):
    user = models.ForeignKey(
        get_user_model(), related_name="saved_grid_views", on_delete=models.CASCADE
    )
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.TextField()
    source = GenericForeignKey("source_content_type", "source_object_id")
    filters = models.JSONField(null=True, blank=True)
    column_defs = models.JSONField(default={})

    class Meta:
        unique_together = ("user", "source_content_type", "source_object_id")

    def grid_config(self):
        return {
            "filters": self.filters,
            "columnDefs": self.column_defs,
        }


@receiver(post_save, sender=UserDataTableView)
def save_user_data_table_view(instance, **kwargs):
    log_event(
        instance.user,
        EventLog.TYPE_DATA_TABLE_VIEW_SAVED,
        instance.source,
    )
