import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories
from dataworkspace.apps.eventlog.models import EventLog


@pytest.mark.django_db
def test_unauthenticated_managed_data(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:managed_data:dataset-stats"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_one_published_dataset_returns_count(client, user):
    client.force_login(user)
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=True,
    )
    response = client.get(reverse("api-v2:managed_data:dataset-stats"))
    managed_data = response.json()["results"][0]
    assert managed_data["count"] == 1
    managed_data_url = f"{reverse('datasets:find_datasets')}?q=&sort=relevance&my_datasets=owned"
    assert managed_data["managed_data_url"] == managed_data_url
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_multiple_published_datasets_return_count(client, user):
    client.force_login(user)
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=True,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is another dataset",
        published=True,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="and another",
        published=True,
    )
    response = client.get(reverse("api-v2:managed_data:dataset-stats"))
    managed_data = response.json()["results"][0]
    assert managed_data["count"] == 3
    managed_data_url = f"{reverse('datasets:find_datasets')}?q=&sort=relevance&my_datasets=owned"
    assert managed_data["managed_data_url"] == managed_data_url
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_unpublished_dataset_does_not_return_count(client, user):
    client.force_login(user)
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=False,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is another dataset",
        published=False,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="and another",
        published=False,
    )
    response = client.get(reverse("api-v2:managed_data:dataset-stats"))
    managed_data = response.json()["results"]
    assert managed_data == []
    assert response.status_code == status.HTTP_200_OK
