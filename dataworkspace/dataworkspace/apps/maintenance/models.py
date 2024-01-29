from django.db import models
import bleach


class MaintenanceSettings(models.Model):
    maintenance_text = models.CharField(
        help_text="This is the main content of the maintenance page. You can use HTML &lt;br&gt; tags to format the text."
    )
    maintenance_toggle = models.BooleanField()
    # contact_email = models.EmailField()

    def save(self, *args, **kwargs):
        self.maintenance_text = bleach.clean(self.maintenance_text, tags=["br"], strip=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return "Maintenance Settings"

    class Meta:
        verbose_name_plural = "settings"
