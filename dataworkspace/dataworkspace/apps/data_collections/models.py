from django.conf import settings
from django.db import models

from dataworkspace.apps.core.models import DeletableTimestampedUserModel


class Collection(DeletableTimestampedUserModel):
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False, unique=True)
    name = models.CharField(blank=False, null=False, max_length=128)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"

    def __str__(self):
        return self.name
