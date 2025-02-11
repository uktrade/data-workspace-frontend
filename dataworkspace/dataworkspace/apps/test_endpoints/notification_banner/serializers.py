from rest_framework import serializers

from dataworkspace.apps.notification_banner.models import (
    NotificationBanner,
)


class NotificationBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationBanner
        fields = (
            "id",
            "last_chance_days",
            "end_date",
        )
