import uuid

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.fields import DateTimeField

from dataworkspace.tests.api_v1.base import BaseAPIViewTest
from dataworkspace.tests import factories


@pytest.mark.django_db
class TestEventLogAPIView(BaseAPIViewTest):
    url = reverse('api-v1:eventlog:events')
    factory = factories.DatasetLinkDownloadEventFactory
    pagination_class = (
        'dataworkspace.apps.api_v1.eventlog.views.EventLogCursorPagination.page_size'
    )

    def expected_response(self, eventlog):
        return {
            'event_type': eventlog.get_event_type_display(),
            'id': eventlog.id,
            'related_object': {
                'id': str(eventlog.related_object.id)
                if type(eventlog.related_object.id) == uuid.UUID
                else eventlog.related_object.id,
                'name': eventlog.related_object.name,
                'type': eventlog.related_object.get_type_display(),
            },
            'timestamp': DateTimeField().to_representation(eventlog.timestamp),
            'user_id': eventlog.user.id,
            'extra': eventlog.extra,
        }

    @pytest.mark.parametrize(
        'event_log_factory',
        (
            factories.DatasetLinkDownloadEventFactory,
            factories.DatasetQueryDownloadEventFactory,
            factories.ReferenceDatasetDownloadEventFactory,
        ),
    )
    def test_success(self, unauthenticated_client, event_log_factory):
        eventlog1 = event_log_factory()
        eventlog2 = event_log_factory()
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['results'] == sorted(
            [self.expected_response(eventlog1), self.expected_response(eventlog2)],
            key=lambda x: x['id'],
        )
