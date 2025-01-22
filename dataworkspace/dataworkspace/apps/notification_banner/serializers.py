from rest_framework import serializers

from dataworkspace.apps.notification_banner.models import NotificationBanner


class NotificationBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationBanner
        fields = "__all__"
