import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories


@pytest.mark.django_db
def test_unauthenticated_your_bookmarks(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_authenticated_user_empty_bookmarks(client, user):
    client.force_login(user)
    response = client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    response_data = response.json()
    assert len(response_data["results"]) == 0


@pytest.mark.django_db
def test_bookmarking_and_return_only_bookmarked_datasets(client, user):
    client.force_login(user)
    d1 = factories.DataSetFactory.create()
    d1.toggle_bookmark(user)

    d2 = factories.DataSetFactory.create()
    d2.toggle_bookmark(user)

    d3 = factories.DataSetFactory.create()

    response = client.get(reverse("api-v2:your_bookmarks:dataset-list"))
    your_bookmarks = response.json()

    assert len(your_bookmarks["results"]) == 2
    assert response.status_code == status.HTTP_200_OK
