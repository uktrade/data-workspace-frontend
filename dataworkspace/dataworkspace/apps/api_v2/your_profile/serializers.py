from rest_framework import serializers
from django.db.models import QuerySet

from dataworkspace.apps.accounts.models import (
    Profile
)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "user",
            "show_bookmarks",
            "show_recent_collections",
            "show_recent_items",
            "show_recent_tools"
        ]
