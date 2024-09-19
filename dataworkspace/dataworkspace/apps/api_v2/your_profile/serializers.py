from rest_framework import serializers

from dataworkspace.apps.accounts.models import (
    Profile
)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "show_bookmarks",
            "show_recent_collections",
            "show_recent_items",
            "show_recent_tools"
        ]
