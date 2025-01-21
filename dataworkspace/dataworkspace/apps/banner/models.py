from django.db import models
import bleach


class BannerSettings(models.Model):
    banner_text = models.CharField(
        help_text="This is the main content of the banner page. You can use HTML &lt;br&gt; tags to format the text."
    )
    banner_toggle = models.BooleanField()
    banner_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        self.banner_text = bleach.clean(self.banner_text, tags=["br"], strip=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return "Banner Settings"

    class Meta:
        verbose_name_plural = "settings"
