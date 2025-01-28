from django.contrib import admin, messages

from dataworkspace.apps.core.admin import CSPRichTextEditorMixin
from dataworkspace.apps.notification_banner.forms import NotificationBannerForm
from dataworkspace.apps.notification_banner.models import NotificationBanner


@admin.register(NotificationBanner)
class NotificationBannerSettingsAdmin(CSPRichTextEditorMixin, admin.ModelAdmin):
    form = NotificationBannerForm
    list_display = ("campaign_name", "content", "published", "end_date")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.published:
            self.message_user(
                request, "Notification Banner has been published", level=messages.SUCCESS
            )
        else:
            self.message_user(
                request, "Notification Banner has been unpublished", level=messages.SUCCESS
            )
