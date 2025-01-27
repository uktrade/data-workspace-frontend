from django.db import models
import bleach
from jsonschema import ValidationError

from dataworkspace.apps.core.models import RichTextField


class NotificationBanner(models.Model):
    content = RichTextField(default=False, null=True)
    published = models.BooleanField(default=False)
    end_date = models.DateField(default=False, null=True)

    def save(self, *args, **kwargs):
        self.content = bleach.clean(self.content, tags=["br"], strip=True)
        # Create only one NotificationBanner instance
        if not self.pk and NotificationBanner.objects.filter(published=True).exists():
            # This below line will render error by breaking the page
            raise ValidationError(
                "There can be only one NotificationBanner you can not add another"
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return "Notification Banner Settings"

    class Meta:
        verbose_name_plural = "settings"
