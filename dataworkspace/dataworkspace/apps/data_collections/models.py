from ckeditor.fields import RichTextField

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from dataworkspace.apps.core.models import DeletableTimestampedUserModel
from dataworkspace.apps.datasets.models import DataSet


class Collection(DeletableTimestampedUserModel):
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False, unique=True)
    name = models.CharField(blank=False, null=False, max_length=128)
    description = RichTextField(null=False, blank=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    datasets = models.ManyToManyField(DataSet, related_name="datasets", blank=True)

    published = models.BooleanField(default=False)
    published_at = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        slug = slugify(self.name)

        self.slug = slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"

    def __str__(self):
        return self.name
