import uuid

from django.conf import settings
from django.db import models

from dataworkspace.apps.core.models import DeletableTimestampedUserModel


class Collection(DeletableTimestampedUserModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(blank=False, null=False, max_length=128)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"

    def __str__(self):
        return self.name
