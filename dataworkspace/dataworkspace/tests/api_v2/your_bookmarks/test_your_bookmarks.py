import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories
from dataworkspace.apps.datasets.models import EventLog


@pytest.mark.django_db
def test_unauthenticated_your_bookmarks(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_ordering_and_filtering_bookmarked_items(client, user):
    client.force_login(user)
    user_event1 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.DataSetFactory.create(),
    )
    user_event2 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.DataSetFactory.create(),
    )
    user_event3 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.DataSetFactory.create(),
    )
    response = client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    your_bookmarks = response.json()
    assert len(your_bookmarks["results"]) == 3
    assert your_bookmarks["results"][0]["id"] == user_event3.id
    assert your_bookmarks["results"][1]["id"] == user_event2.id
    assert your_bookmarks["results"][2]["id"] == user_event1.id
    assert response.status_code == status.HTTP_200_OK


def test_authenticated_user_empty_bookmarks(client, user):
    client.force_login(user)

    response = client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert len(response_data["results"]) == 0
