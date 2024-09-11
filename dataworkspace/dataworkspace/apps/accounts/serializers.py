from dataworkspace.apps.api_v1.core import serializers
from dataworkspace.apps.accounts.models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"
