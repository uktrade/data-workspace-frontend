from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.conftest import get_staff_client, get_staff_user_data


def test_collection(client):
    user = factories.UserFactory(is_superuser=True)
    client = get_staff_client(get_staff_user_data("", user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=True
    )

    assert c.slug == "test-collections"

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_slug": c.slug},
        )
    )
    assert response.status_code == 200
    assert "<p>test collections description</p>" in response.content.decode(response.charset)


def test_unpublished_raises_404(client):
    user = factories.UserFactory()
    client = get_staff_client(get_staff_user_data("my_database", user))

    c = factories.CollectionFactory.create(
        name="test-collections", description="test collections description", published=False
    )

    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_slug": c.slug},
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
            kwargs={"collections_slug": c.slug},
        )
    )

    assert response.status_code == 404
