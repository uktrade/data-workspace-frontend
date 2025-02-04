import uuid

from django.contrib.auth import get_user_model
from django.db import models

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.models import TimeStampedModel


class ApplicationInstanceArangoUsers(TimeStampedModel):
    """
    Model for tracking temporary user credentials against application instances
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_username = models.CharField(max_length=256)
    application_instance = models.ForeignKey(ApplicationInstance, on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=["db_username"])]


class ArangoUser(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="arango_user"
    )
    username = models.CharField(max_length=256, db_index=True)
    deleted_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_date",)
