from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.conftest import get_staff_client, get_staff_user_data


def test_collection(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_staff_client(get_staff_user_data("", user))

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
    client = get_staff_client(get_staff_user_data("my_database", user))

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
    client = get_staff_client(get_staff_user_data("", user))

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


def test_reference_dataset_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_staff_client(get_staff_user_data("", user))

    rds = factories.ReferenceDatasetFactory(
        published=True, description="reference dataset example description"
    )

    c = factories.CollectionFactory.create(
        name="test-collections-with-reference-dataset",
        description="test collections description for reference datasets",
        published=True,
    )

    c.datasets.add(rds.reference_dataset_inheriting_from_dataset)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    assert "Reference Dataset" in response.content.decode(response.charset)
