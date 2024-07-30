import uuid
import re
from django.db import models
from django.contrib.auth import get_user_model
from dataworkspace.apps.core.models import TimeStampedModel, RichTextField
from dataworkspace.apps.applications.models import ApplicationInstance


class ApplicationInstanceArangoUsers(TimeStampedModel):
    """
    Model for tracking temporary user credentials against application instances
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_username = models.CharField(max_length=256)
    application_instance = models.ForeignKey(ApplicationInstance, on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=["db_username"])]


class ArangoTeam(TimeStampedModel):
    """
    Arango Team model containing defining team schema permissions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256, unique=True)
    database_name = models.CharField(max_length=63, unique=True)

    member = models.ManyToManyField(get_user_model(), through="ArangoTeamMembership")
    notes = RichTextField(null=True, blank=True)

    class Meta:
        verbose_name = "ArangoTeam"
        verbose_name_plural = "ArangoTeams"

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.database_name:
            self.database_name = "team_" + re.sub("[^a-z0-9]", "_", self.name.lower())[:63]
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class ArangoTeamMembership(TimeStampedModel):
    team = models.ForeignKey(ArangoTeam, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)

    class Meta:
        unique_together = ("team_id", "user_id")
