import uuid

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.fields import DateTimeField

from dataworkspace.tests import factories


def expected_event_log_response(eventlog):
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
        'user': {
            'id': eventlog.user.id,
            'email': eventlog.user.email,
            'first_name': eventlog.user.first_name,
            'last_name': eventlog.user.last_name,
        },
        'extra': eventlog.extra,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    'event_log_factory',
    (
        factories.DatasetLinkDownloadEventFactory,
        factories.DatasetQueryDownloadEventFactory,
        factories.ReferenceDatasetDownloadEventFactory,
    ),
)
def test_success(unauthenticated_client, event_log_factory):
    eventlog1 = event_log_factory()
    eventlog2 = event_log_factory()
    response = unauthenticated_client.get(reverse('api-v1:eventlog:events'))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['results'] == [
        expected_event_log_response(eventlog2),
        expected_event_log_response(eventlog1),
    ]


@pytest.mark.django_db
def test_no_data(unauthenticated_client):
    response = unauthenticated_client.get(reverse('api-v1:eventlog:events'))
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize('method', ('delete', 'patch', 'post', 'put'))
def test_invalid_methods(unauthenticated_client, method):
    response = getattr(unauthenticated_client, method)(
        reverse('api-v1:eventlog:events')
    )
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
