import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories
from dataworkspace.apps.eventlog.models import EventLog


@pytest.mark.django_db
def test_unathenticated_your_bookmarks(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:your_bookmarks"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_ordering_and_filtering_bookmarked_items(client, user):
    client.force_login(user)
    user_event1 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.ReferenceDatasetFactory.create(),
    )
    user_event2 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.ReferenceDatasetFactory.create(),
    )
    user_event3 = factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.ReferenceDatasetFactory.create(),
    )
    factories.EventLogFactory(
        event_type=EventLog.TYPE_DATASET_BOOKMARKED,
        related_object=factories.ReferenceReferenceDatasetFactory.create(),
    )

    response = client.get(reverse("api-v2:your_bookmarks"))
    bookmarks = response.json()
    assert len(bookmarks["results"]) == 3
    assert bookmarks["results"][0]["id"] == user_event3.id
    assert bookmarks["results"][1]["id"] == user_event2.id
    assert bookmarks["results"][2]["id"] == user_event1.id
    assert response.status_code == status.HTTP_200_OK
