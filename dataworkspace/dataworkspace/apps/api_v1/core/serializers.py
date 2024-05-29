from rest_framework import serializers

from dataworkspace.apps.core.models import (
    UserSatisfactionSurvey,
    NewsletterSubscription,
    Team,
    UserInlineFeedbackSurvey,
)


class UserSatisfactionSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSatisfactionSurvey
        fields = "__all__"


class UserInlineFeedbackSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInlineFeedbackSurvey
        fields = "__all__"


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = "__all__"


class TeamSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    id = serializers.UUIDField()

    class Meta:
        model = Team
        fields = ("id", "name", "schema_name", "members")

    def get_members(self, team):
        return [x.id for x in team.member.all()]
