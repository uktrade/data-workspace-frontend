from rest_framework import serializers

from dataworkspace.apps.datasets.models import (
    PendingAuthorizedUsers,
)


class PendingAuthorizedUsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingAuthorizedUsers
        fields = (
            "created_by_id",
            "user_ids",
        )
