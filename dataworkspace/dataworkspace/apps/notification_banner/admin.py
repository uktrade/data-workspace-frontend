from django.contrib import admin

from dataworkspace.apps.notification_banner.models import NotificationBanner


@admin.register(NotificationBanner)
class BannerSettingsAdmin(admin.ModelAdmin):
    list_display = ("banner_text", "banner_link_text", "banner_link", "banner_live", "banner_end_date")
