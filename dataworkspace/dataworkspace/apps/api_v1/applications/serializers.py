from rest_framework import serializers

from dataworkspace.apps.applications.models import ApplicationInstance


class ApplicationInstanceSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    application_template_name = serializers.CharField(source="application_template.name")

    class Meta:
        model = ApplicationInstance
        fields = (
            "id",
            "owner_id",
            "public_host",
            "spawner",
            "application_template_name",
            "spawner_application_instance_id",
            "spawner_created_at",
            "spawner_stopped_at",
            "spawner_cpu",
            "spawner_memory",
            "state",
            "proxy_url",
            "cpu",
            "memory",
            "commit_id",
        )

    def get_state(self, obj):
        return obj.get_state_display()
