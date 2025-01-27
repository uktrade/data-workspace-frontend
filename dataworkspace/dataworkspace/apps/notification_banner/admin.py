from django.contrib import admin, messages

from dataworkspace.apps.notification_banner.models import NotificationBanner


@admin.register(NotificationBanner)
class NotificationBannerSettingsAdmin(admin.ModelAdmin):
    list_display = ("content", "published", "end_date")

    # disables the option to add a new Notification Banner
    def has_add_permission(self, request, obj=None):
        return False
