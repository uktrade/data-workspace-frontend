from datetime import datetime
from django.db import models
import bleach
from jsonschema import ValidationError

from dataworkspace.apps.core.models import RichTextField


class NotificationBanner(models.Model):
    content = RichTextField(default='blah')
    published = models.BooleanField(default=False)
    end_date = models.DateField(default=datetime.now())

    def save(self, *args, **kwargs):
        self.content = bleach.clean(self.content, tags=["br"], strip=True)
        # Create only one NotificationBanner instance
        if not self.pk and NotificationBanner.objects.exists():
            # This below line will render error by breaking page, you will see
            raise ValidationError(
                "There can be only one NotificationBanner you can not add another"
            )
            return None
        return super(NotificationBanner, self).save(*args, **kwargs)

    def __str__(self):
        return "Banner Settings"

    class Meta:
        verbose_name_plural = "settings"
