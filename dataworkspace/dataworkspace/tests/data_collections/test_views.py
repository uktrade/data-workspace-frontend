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


def test_authorised_user_attempting_delete_dataset_membership(user, other_user):
    client_user = get_client(get_user_data(user))
    client_other_user = get_client(get_user_data(other_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        published=True,
        owner=user,
    )

    # Create a dataset and add it to the collection
    dataset = factories.DatacutDataSetFactory(published=True, name="Datacut dataset")
    c.datasets.add(dataset)
    membership = c.dataset_collections.all()[0]
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Datacut dataset<" in response.content.decode(response.charset)

    # Ensure that a user that isn't the owner can't remove it
    response = client_other_user.post(
        reverse(
            "data_collections:collection_data_membership",
            kwargs={"collections_id": c.id, "data_membership_id": membership.id},
        )
    )
    assert response.status_code == 404
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Datacut dataset<" in response.content.decode(response.charset)

    # But the owner user can remove the dataset from the collection page
    response = client_user.post(
        reverse(
            "data_collections:collection_data_membership",
            kwargs={"collections_id": c.id, "data_membership_id": membership.id},
        )
    )
    assert response.status_code == 302
    assert response["Location"] == reverse(
        "data_collections:collections_view",
        kwargs={"collections_id": c.id},
    )
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Datacut dataset<" not in response.content.decode(response.charset)
    assert "Datacut dataset has been removed from this collection" in response.content.decode(
        response.charset
    )


def test_authorised_user_attempting_delete_visualisation_membership(user, other_user):
    client_user = get_client(get_user_data(user))
    client_other_user = get_client(get_user_data(other_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        published=True,
        owner=user,
    )

    # Create a visualisation and add it to the collection
    visualisation = factories.VisualisationCatalogueItemFactory(
        personal_data="personal", name="Visualisation"
    )
    c.visualisation_catalogue_items.add(visualisation)
    membership = c.visualisation_collections.all()[0]
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Visualisation<" in response.content.decode(response.charset)

    # Ensure that a user that isn't the owner can't remove it
    response = client_other_user.post(
        reverse(
            "data_collections:collection_visualisation_membership",
            kwargs={"collections_id": c.id, "visualisation_membership_id": membership.id},
        )
    )
    assert response.status_code == 404
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Visualisation<" in response.content.decode(response.charset)

    # But the owner user can remove the visualisation from the collection page
    response = client_user.post(
        reverse(
            "data_collections:collection_visualisation_membership",
            kwargs={"collections_id": c.id, "visualisation_membership_id": membership.id},
        )
    )
    assert response.status_code == 302
    assert response["Location"] == reverse(
        "data_collections:collections_view",
        kwargs={"collections_id": c.id},
    )
    response = client_user.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert ">Visualisations<" not in response.content.decode(response.charset)
    assert "Visualisation has been removed from this collection" in response.content.decode(
        response.charset
    )


def test_authorised_user_attempting_to_add_new_catalogue_membership(staff_user):
    client_user = get_client(get_user_data(staff_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        published=True,
        owner=staff_user,
    )

    # Create a dataset to be added to the collection
    visualisation = factories.VisualisationCatalogueItemFactory(
        published=True, name="Visualisation catalogue item"
    )

    response = client_user.post(
        reverse(
            "data_collections:add_collection_data_membership",
            kwargs={"collections_id": c.id, "catalogue_id": visualisation.id},
        )
    )
    assert response.status_code == 302


def test_reference_dataset_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

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
