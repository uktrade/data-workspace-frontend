from django.contrib import admin

from dataworkspace.apps.notification_banner.models import NotificationBanner


@admin.register(NotificationBanner)
class BannerSettingsAdmin(admin.ModelAdmin):
    list_display = ("content", "published", "end_date")
