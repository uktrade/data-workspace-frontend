from django.db.models import Q, TextField

from django.urls import reverse
from rest_framework import serializers

from django.db.models.functions import Cast

from dataworkspace.apps.accounts.models import (
    Profile
)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "bookmarks"
            # "recent_collections"
            # "recent_items"
            # "recent_tools"
        ]
