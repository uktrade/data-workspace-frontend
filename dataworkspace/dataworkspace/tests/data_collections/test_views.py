from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.conftest import get_client, get_user_data
from dataworkspace.apps.data_collections.models import CollectionUserMembership


def test_collection(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description"
    )

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert "test collections description" in response.content.decode(response.charset)


def test_deleted_raises_404(client):
    user = factories.UserFactory()
    client = get_client(get_user_data(user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", deleted=True
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
        name="test-collections", description="test collections description"
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
    dataset.tags.set(
        [
            factories.SourceTagFactory(name="The Source"),
            factories.TopicTagFactory(name="The Topic"),
        ]
    )

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description"
    )

    c.datasets.add(dataset)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    response_text = response.content.decode(response.charset)
    assert "Datacut dataset" in response_text
    assert "The Source" in response_text
    assert "The Topic" in response_text


def test_reference_dataset_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    reference_dataset = factories.ReferenceDatasetFactory(
        published=True, short_description="reference dataset example description"
    )
    reference_dataset.tags.set(
        [
            factories.SourceTagFactory(name="The Source"),
            factories.TopicTagFactory(name="The Topic"),
        ]
    )

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description"
    )

    c.datasets.add(reference_dataset.reference_dataset_inheriting_from_dataset)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    response_text = response.content.decode(response.charset)
    assert "reference dataset example description" in response_text
    assert "The Source" in response_text
    assert "The Topic" in response_text


def test_visualisation_can_be_added(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_client(get_user_data(user))

    catalogue_item = factories.VisualisationCatalogueItemFactory(
        personal_data="personal", name="dummy visualisation catalogue item"
    )
    catalogue_item.tags.set(
        [
            factories.SourceTagFactory(name="The Source"),
            factories.TopicTagFactory(name="The Topic"),
        ]
    )

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description"
    )

    c.visualisation_catalogue_items.add(catalogue_item)

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 200
    response_text = response.content.decode(response.charset)
    assert "dummy visualisation catalogue item" in response_text
    assert "The Source" in response_text
    assert "The Topic" in response_text


def test_authorised_user_attempting_delete_dataset_membership(user, other_user):
    client_user = get_client(get_user_data(user))
    client_other_user = get_client(get_user_data(other_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
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
    response = client_other_user.get(
        reverse(
            "data_collections:collection_data_membership_confirm_removal",
            kwargs={"collections_id": c.id, "data_membership_id": membership.id},
        )
    )
    assert response.status_code == 404
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
    response = client_user.get(
        reverse(
            "data_collections:collection_data_membership_confirm_removal",
            kwargs={"collections_id": c.id, "data_membership_id": membership.id},
        )
    )
    assert response.status_code == 200
    assert (
        "Are you sure you want to remove Datacut dataset from the collection?"
        in response.content.decode(response.charset)
    )
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
    response = client_other_user.get(
        reverse(
            "data_collections:collection_visualisation_membership_confirm_removal",
            kwargs={"collections_id": c.id, "visualisation_membership_id": membership.id},
        )
    )
    assert response.status_code == 404
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
    response = client_user.get(
        reverse(
            "data_collections:collection_visualisation_membership_confirm_removal",
            kwargs={"collections_id": c.id, "visualisation_membership_id": membership.id},
        )
    )
    assert response.status_code == 200
    assert (
        "Are you sure you want to remove Visualisation from the collection?"
        in response.content.decode(response.charset)
    )
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


def test_collection_selection_page(staff_user, staff_client):
    c1 = factories.CollectionFactory.create(
        name="test-collections-1",
        description="test collections 1",
        owner=staff_user,
    )
    c2 = factories.CollectionFactory.create(
        name="test-collections-2",
        description="test collections 2",
        owner=staff_user,
    )
    c3 = factories.CollectionFactory.create(
        name="test-collections-3",
        description="test collections 3",
        owner=staff_user,
        deleted=True,
    )
    visualisation = factories.VisualisationCatalogueItemFactory(
        published=True, name="Visualisation catalogue item"
    )
    response = staff_client.get(
        reverse(
            "data_collections:visualisation_select_collection_for_membership",
            kwargs={"dataset_id": visualisation.id},
        )
    )
    assert response.status_code == 200
    assert c1.name in response.content.decode(response.charset)
    assert c2.name in response.content.decode(response.charset)
    assert c3.name not in response.content.decode(response.charset)


def test_authorised_user_attempting_to_add_new_catalogue_membership(staff_user):
    client = get_client(get_user_data(staff_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        owner=staff_user,
    )

    # Create a dataset to be added to the collection
    visualisation = factories.VisualisationCatalogueItemFactory(
        published=True, name="Visualisation catalogue item"
    )

    response = client.post(
        reverse(
            "data_collections:visualisation_select_collection_for_membership",
            kwargs={"dataset_id": visualisation.id},
        ),
        data={"collection": c.id},
    )
    assert response.status_code == 302


def test_authorised_user_attempting_to_add_new_collection_dataset_membership(staff_user):
    client = get_client(get_user_data(staff_user))

    # Create the collection
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        owner=staff_user,
    )

    dataset = factories.DatacutDataSetFactory(published=True, name="Datacut dataset")

    response = client.post(
        reverse(
            "data_collections:dataset_select_collection_for_membership",
            kwargs={"dataset_id": dataset.id},
        ),
        data={"collection": c.id},
    )
    assert response.status_code == 302


def test_authorised_user_attempting_to_add_new_collection_reference_dataset_membership(
    staff_client, staff_user
):
    c = factories.CollectionFactory.create(
        name="test-collections",
        description="test collections description",
        owner=staff_user,
    )

    rds = factories.ReferenceDatasetFactory(
        published=True, description="reference dataset example description"
    )

    response = staff_client.post(
        reverse(
            "data_collections:dataset_select_collection_for_membership",
            kwargs={"dataset_id": rds.reference_dataset_inheriting_from_dataset.id},
        ),
        data={"collection": c.id},
    )
    assert response.status_code == 302


def test_user_page(client):
    user = factories.UserFactory(is_superuser=True)
    user2 = factories.UserFactory()
    client = get_client(get_user_data(user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", owner=user
    )
    CollectionUserMembership.objects.create(collection=c, user=user2)

    response = client.get(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        )
    )
    assert response.status_code == 200
    assert user2.email in response.content.decode(response.charset)


def test_user_not_owner_raises_404(client):
    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description"
    )

    response = client.get(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        )
    )

    assert response.status_code == 404


def test_add_user_invalid_email_input(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": "imnotanemailaddress"},
    )
    assert response.status_code == 200
    assert "You must enter a valid email address" in response.content.decode(response.charset)


def test_add_user_email_provided_doesnt_exist(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": "bob2@test.com"},
    )
    assert response.status_code == 200
    assert (
        "The user you are sharing with must have a DIT staff SSO account"
        in response.content.decode(response.charset)
    )


def test_add_user_already_exists_on_collection(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    user2 = factories.UserFactory()
    CollectionUserMembership.objects.create(collection=c, user=user2)
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": user2.email},
    )
    assert response.status_code == 200
    assert f"{user2.email} already has access to this collection" in response.content.decode(
        response.charset
    )


def test_add_user_already_already_owner_of_collection(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": user.email},
    )
    assert response.status_code == 200
    assert f"{user.email} already has access to this collection" in response.content.decode(
        response.charset
    )


def test_add_user_not_the_owner(client, user):
    c = factories.CollectionFactory.create(name="test-collections")
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": "terrence@test.com"},
    )
    assert response.status_code == 404


def test_add_user_success(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    user2 = factories.UserFactory()
    member_count = CollectionUserMembership.objects.all().count()
    response = client.post(
        reverse(
            "data_collections:collection-users",
            kwargs={"collections_id": c.id},
        ),
        data={"email": user2.email},
        follow=True,
    )
    assert response.status_code == 200
    assert CollectionUserMembership.objects.all().count() == member_count + 1
    assert user2.email in response.content.decode(response.charset)

def test_remove_user_not_owner(client):
    c = factories.CollectionFactory.create(name="test-collections")
    member = factories.CollectionUserMembershipFactory.create(collection=c)
    response = client.post(
        reverse(
            "data_collections:remove-user",
            kwargs={"user_membership_id": member.id, "collections_id": c.id}
        ),
    )
    assert response.status_code == 404


def test_user_successfully_removed(client, user):
    c = factories.CollectionFactory.create(name="test-collections", owner=user)
    member = factories.CollectionUserMembershipFactory.create(collection=c)
    member_count = CollectionUserMembership.objects.live().count()
    response = client.post(
        reverse(
            "data_collections:remove-user",
            kwargs={"user_membership_id": member.id, "collections_id": c.id}
        ),
        follow=True,
    )
    assert response.status_code == 200
    assert CollectionUserMembership.objects.live().count() == member_count - 1
    assert member.user.email not in response.content.decode(response.charset)

