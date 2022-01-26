from datetime import datetime

from ckeditor.fields import RichTextField
from django.db import models
from django.urls import reverse

from dataworkspace.apps.core.models import TimeStampedUserModel
from dataworkspace.apps.core.storage import S3FileStorage, malware_file_validator


class CaseStudy(TimeStampedUserModel):
    slug = models.SlugField()
    published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(null=True)
    name = models.CharField(max_length=255)
    short_description = models.CharField(max_length=255)
    department_name = models.CharField(max_length=255, blank=True)
    service_name = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=255, blank=True)
    image = models.FileField(
        blank=True,
        storage=S3FileStorage(location="case-studies"),
        validators=[malware_file_validator],
    )
    background = RichTextField(blank=True)
    solution = RichTextField(blank=True)
    impact = RichTextField(blank=True)
    quote_title = models.CharField(max_length=255, blank=True)
    quote_text = RichTextField(blank=True)
    quote_full_name = models.CharField(max_length=255, blank=True)
    quote_department_name = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Case studies"
        ordering = ("-created_date",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_publish_date = self.publish_date

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # If the case study is changing from unpublished to published state
        # update the publish date before saving
        if self.published and not self._original_publish_date:
            self.publish_date = datetime.now()
        # If it's going from published to unpublished, unset the publish date
        elif self._original_publish_date and not self.published:
            self.publish_date = None

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

        self._original_publish_date = self.publish_date

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("case-studies:case-study", args=(self.slug,))
