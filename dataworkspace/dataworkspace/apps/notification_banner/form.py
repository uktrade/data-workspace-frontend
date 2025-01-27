from django import forms
from django.core.exceptions import ValidationError

from dataworkspace.apps.notification_banner.models import NotificationBanner


class NotificationBannerForm(forms.ModelForm):

    class Meta:
        model = NotificationBanner
        fields = "__all__"

    def clean_published(self):
        published = self.cleaned_data('published')
        if published and NotificationBanner.objects.filter(published=True).exclude(pk=self.instance.pk).exists():
            raise ValidationError("ONLY ONE")
        return published
