from rest_framework import serializers
from django.urls import reverse
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.applications.utils import get_tool_url_for_user


class RecentToolsSerializer(serializers.ModelSerializer):
    tool_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EventLog
        fields = (
            "id",
            "timestamp",
            "extra",
            "tool_url",
        )

    def get_tool_url(self, obj):
        if (
            obj.event_type == EventLog.TYPE_USER_TOOL_ECS_STARTED
            and obj.related_object is not None
        ):
            return get_tool_url_for_user(obj.user, obj.related_object.application_template)
        elif obj.event_type == EventLog.TYPE_USER_TOOL_LINK_STARTED and obj.extra is not None:
            if obj.extra["tool"] == "Data Explorer":
                return reverse("applications:data_explorer_redirect")
            elif obj.extra["tool"] == "Superset":
                return reverse("applications:superset_redirect")
            elif obj.extra["tool"] == "Quicksight":
                return reverse("applications:quicksight_redirect")
        return None
