from rest_framework import serializers

from dataworkspace.apps.core.models import UserSatisfactionSurvey


class UserSatisfactionSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSatisfactionSurvey
        fields = '__all__'
