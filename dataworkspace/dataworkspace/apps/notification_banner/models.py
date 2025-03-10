import re

import bleach
from django.db import models
from django.core.exceptions import ValidationError

from dataworkspace.apps.core.models import RichTextField


class NotificationBanner(models.Model):
    campaign_name = models.CharField(
        max_length=255, help_text="To be used as the cookie name(spaces will be removed on save)"
    )
    content = RichTextField()
    last_chance_content = RichTextField(
        blank=True,
        help_text="(Optional) Message to run within 'last_chance_days' window. \
              Will be shown to users that have dismissed or not engaged with the banner.",
        null=True,
    )
    last_chance_days = models.IntegerField(
        blank=True, help_text="(Optional) Days remaining to run 'last chance message'.", null=True
    )
    end_date = models.DateField()
    published = models.BooleanField(default=False)

    def clean(self):
        # Create only one Abc instance
        if not self.pk and NotificationBanner.objects.filter(published=True).exists():
            # This below line will render error by breaking page, you will see

            raise ValidationError(
                "Can't have 'last chance' content without setting the time window in which the message will display."
            )
        elif self.last_chance_days and not self.last_chance_content:
            raise ValidationError(
                "Can't have 'last chance' days remaining without setting the 'last chance' content that will display"
            )

    def save(self, *args, **kwargs):
        self.content = bleach.clean(self.content, tags=["br", "a", "strong", "i"], strip=True)
        self.campaign_name = re.sub(r"[^\w_)+]", "", self.campaign_name)

        return super().save(*args, **kwargs)

    def __str__(self):
        return "Notification Banner"

    class Meta:
        verbose_name_plural = "Notification Banner"
