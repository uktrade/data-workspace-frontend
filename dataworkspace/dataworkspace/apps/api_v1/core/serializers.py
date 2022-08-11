from rest_framework import serializers

from dataworkspace.apps.core.models import UserSatisfactionSurvey, NewsletterSubscription


class UserSatisfactionSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSatisfactionSurvey
        fields = "__all__"


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = "__all__"
