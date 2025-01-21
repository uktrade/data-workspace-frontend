from django.contrib import admin

from dataworkspace.apps.banner.models import BannerSettings


@admin.register(BannerSettings)
class BannerSettingsAdmin(admin.ModelAdmin):
    list_display = ("banner_text", "banner_toggle", "banner_time")
