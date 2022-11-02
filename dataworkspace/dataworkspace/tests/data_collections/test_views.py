from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.conftest import get_client, get_user_data


def test_collection(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=True
    )

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert "test collections description" in response.content.decode(response.charset)


def test_unpublished_raises_404(client):
    user = factories.UserFactory()
    client = get_client(get_user_data(user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=False
    )

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 404


def test_unauthorised_user_raises_404(client):
    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=True
    )

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 404


def test_dataset_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    dataset = factories.DatacutDataSetFactory(published=True, name="Datacut dataset")

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=True
    )

    c.datasets.add(dataset)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    assert "Datacut dataset" in response.content.decode(response.charset)


def test_visualisation_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    catalogue_item = factories.VisualisationCatalogueItemFactory(
        personal_data="personal", name="dummy visualisation catalogue item"
    )

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=True
    )

    c.visualisation_catalogue_items.add(catalogue_item)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    assert "dummy visualisation catalogue item" in response.content.decode(response.charset)
