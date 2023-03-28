import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status
from rest_framework.fields import DateTimeField

from dataworkspace.tests import factories
from dataworkspace.tests.api_v1.base import BaseAPIViewTest


@pytest.mark.django_db
@freeze_time("2020-01-01 00:00:00")
class TestEventLogAPIView(BaseAPIViewTest):
    url = reverse("api-v1:application-instance:instances")
    factory = factories.ApplicationInstanceFactory
    pagination_class = "dataworkspace.apps.api_v1.applications.views.ApplicationInstanceCursorPagination.page_size"

    def expected_response(self, app_instance):
        return {
            "application_template_name": app_instance.application_template.name,
            "commit_id": app_instance.commit_id,
            "cpu": app_instance.cpu,
            "id": str(app_instance.id),
            "memory": app_instance.memory,
            "owner_id": app_instance.owner_id,
            "proxy_url": app_instance.proxy_url,
            "public_host": app_instance.public_host,
            "spawner": app_instance.spawner,
            "spawner_application_instance_id": str(app_instance.spawner_application_instance_id),
            "spawner_cpu": app_instance.spawner_cpu,
            "spawner_created_at": DateTimeField().to_representation(
                app_instance.spawner_created_at
            ),
            "spawner_memory": app_instance.spawner_memory,
            "spawner_stopped_at": DateTimeField().to_representation(
                app_instance.spawner_stopped_at
            ),
            "state": app_instance.get_state_display(),
        }

    @pytest.mark.django_db
    @freeze_time("2020-01-01 00:00:00")
    def test_success(self, unauthenticated_client):
        instance1 = factories.ApplicationInstanceFactory()
        instance2 = factories.ApplicationInstanceFactory()
        response = unauthenticated_client.get(reverse("api-v1:application-instance:instances"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == sorted(
            [self.expected_response(instance1), self.expected_response(instance2)],
            key=lambda x: x["id"],
        )
