import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories


@pytest.mark.django_db
def test_unauthenticated_collections(unauthenticated_client, user):
    factories.CollectionFactory.create(
        name="test-collections", description="test collections description", owner=user
    )
    response = unauthenticated_client.get(reverse("api-v2:collections:collection-list"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_collections_by_order(client, user):
    client.force_login(user)
    dataset = factories.DatacutDataSetFactory(published=True, name="Datacut dataset")
    factories.CollectionFactory(
        name="test-collection-c", description="test collections description", owner=user
    ).datasets.add(dataset)
    factories.CollectionFactory(
        name="test-collection-b", description="test collections description", owner=user
    ).datasets.add(dataset)
    factories.CollectionFactory(
        name="test-collection-a", description="test collections description", owner=user
    ).datasets.add(dataset)
    response = client.get(reverse("api-v2:collections:collection-list"))
    collection_datasets = response.json()
    assert collection_datasets["results"][0]["name"] == "test-collection-a"
    assert collection_datasets["results"][1]["name"] == "test-collection-b"
    assert collection_datasets["results"][2]["name"] == "test-collection-c"
    assert response.status_code == status.HTTP_200_OK
