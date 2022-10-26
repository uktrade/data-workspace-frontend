from django.conf import settings
from django.db import models, IntegrityError, transaction
from django.utils.text import slugify

from dataworkspace.apps.core.models import DeletableTimestampedUserModel


class Collection(DeletableTimestampedUserModel):
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False, unique=True)
    name = models.CharField(blank=False, null=False, max_length=128)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    published = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        create = self.pk is None
        if create:
            for i in range(0, 20):
                slug = slugify(self.name) + ("" if i == 0 else f"-{i}")
                self.slug = slug
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                except IntegrityError:
                    if i == 19:
                        raise
                else:
                    break
        else:
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"

    def __str__(self):
        return self.name
