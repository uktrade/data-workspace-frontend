from django.contrib import admin

from dataworkspace.apps.core.admin import CSPRichTextEditorMixin
from dataworkspace.apps.notification_banner.models import NotificationBanner


@admin.register(NotificationBanner)
class BannerSettingsAdmin(CSPRichTextEditorMixin, admin.ModelAdmin):
    list_display = ("campaign_name", "content", "published", "end_date")
