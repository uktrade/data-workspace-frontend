from rest_framework import serializers

from dataworkspace.apps.banner.models import BannerSettings


class BannerSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BannerSettings
        fields = "__all__"
