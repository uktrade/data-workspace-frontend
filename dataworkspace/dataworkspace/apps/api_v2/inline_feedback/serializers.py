from rest_framework import serializers

from dataworkspace.apps.core.models import UserInlineFeedbackSurvey


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInlineFeedbackSurvey
        fields = [
            "id",
            "location",
            "was_this_page_helpful",
            "inline_feedback_choices",
            "more_detail",
        ]
