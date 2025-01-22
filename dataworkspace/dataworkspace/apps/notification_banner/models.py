from datetime import datetime
from django.db import models
import bleach


class NotificationBanner(models.Model):
    banner_text = models.CharField(max_length=255)
    banner_link_text = models.CharField(max_length=255, blank=True)
    banner_link = models.CharField(max_length=255, blank=True)
    banner_live = models.BooleanField(default=False)
    banner_end_date = models.DateField(default=datetime.now())

    def save(self, *args, **kwargs):
        self.banner_text = bleach.clean(self.banner_text, tags=["br"], strip=True)
        self.banner_link_text = bleach.clean(self.banner_link_text, tags=["br"], strip=True)
        self.banner_link = bleach.clean(self.banner_link, tags=["br"], strip=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return "Banner Settings"

    class Meta:
        verbose_name_plural = "settings"
