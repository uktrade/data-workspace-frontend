import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.fields import DateTimeField

from dataworkspace.tests import factories
from dataworkspace.tests.api_v1.base import BaseAPIViewTest
from dataworkspace.tests.factories import ApplicationInstanceReportFactory


@pytest.mark.django_db
class TestEventLogAPIView(BaseAPIViewTest):
    url = reverse('api-v1:application-instance:instances')
    factory = factories.ApplicationInstanceReportFactory
    pagination_class = 'dataworkspace.apps.api_v1.applications.views.ApplicationInstanceReportCursorPagination.page_size'

    def expected_response(self, app_instance):
        return {
            'commit_id': app_instance.commit_id,
            'cpu': app_instance.cpu,
            'id': str(app_instance.id),
            'memory': app_instance.memory,
            'owner_id': app_instance.owner_id,
            'proxy_url': app_instance.proxy_url,
            'public_host': app_instance.public_host,
            'spawner': app_instance.spawner,
            'spawner_application_instance_id': str(
                app_instance.spawner_application_instance_id
            ),
            'spawner_application_template_options': app_instance.spawner_application_template_options,
            'spawner_cpu': app_instance.spawner_cpu,
            'spawner_created_at': DateTimeField().to_representation(
                app_instance.spawner_created_at
            ),
            'spawner_memory': app_instance.spawner_memory,
            'spawner_stopped_at': DateTimeField().to_representation(
                app_instance.spawner_stopped_at
            ),
            'state': app_instance.get_state_display(),
        }

    @pytest.mark.django_db
    def test_success(self, unauthenticated_client):
        instance1 = ApplicationInstanceReportFactory()
        instance2 = ApplicationInstanceReportFactory()
        response = unauthenticated_client.get(
            reverse('api-v1:application-instance:instances')
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['results'] == sorted(
            [self.expected_response(instance1), self.expected_response(instance2)],
            key=lambda x: x['id'],
        )
