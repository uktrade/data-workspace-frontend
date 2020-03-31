from rest_framework import serializers

from dataworkspace.apps.applications.models import ApplicationInstanceReport


class ApplicationInstanceReportSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationInstanceReport
        fields = (
            'id',
            'owner_id',
            'public_host',
            'spawner',
            'spawner_application_template_options',
            'spawner_application_instance_id',
            'spawner_created_at',
            'spawner_stopped_at',
            'spawner_cpu',
            'spawner_memory',
            'state',
            'proxy_url',
            'cpu',
            'memory',
            'commit_id',
        )

    def get_state(self, obj):
        return obj.get_state_display()
