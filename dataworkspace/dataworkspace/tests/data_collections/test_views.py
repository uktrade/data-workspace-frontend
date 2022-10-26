from django.urls import reverse

from dataworkspace.tests import factories


def test_collection(client):
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
