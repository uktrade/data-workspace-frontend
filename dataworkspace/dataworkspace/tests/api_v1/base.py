import mock
import pytest
from factory.django import DjangoModelFactory
from rest_framework import status


@pytest.mark.django_db
class BaseAPIViewTest:
    url: str = None
    factory: DjangoModelFactory = None
    pagination_class: str = None

    def test_pagination(self, unauthenticated_client):
        self.factory.create_batch(3)
        with mock.patch(self.pagination_class, 2):
            response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["next"] is not None

    def test_no_data(self, unauthenticated_client):
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("method", ("delete", "patch", "post", "put"))
    def test_invalid_methods(self, unauthenticated_client, method):
        response = getattr(unauthenticated_client, method)(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
