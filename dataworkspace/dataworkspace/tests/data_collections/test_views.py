from django.urls import reverse

from dataworkspace.tests import factories


def test_collection(client):
    c = factories.CollectionFactory.create(
        slug="test-collections", description="test collections description"
    )
    response = client.get(
        reverse(
            "data_collections:collections_view",
            kwargs={"collections_slug": c.slug},
        )
    )
    assert response.status_code == 200
    assert "<p>test collections description</p>" in response.content.decode(response.charset)
