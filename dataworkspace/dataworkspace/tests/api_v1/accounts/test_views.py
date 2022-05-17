import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status

from dataworkspace.tests import factories
from dataworkspace.tests.api_v1.base import BaseAPIViewTest


@pytest.mark.django_db
class TestUserAPIView(BaseAPIViewTest):
    url = reverse("api-v1:account:users")
    factory = factories.UserFactory
    pagination_class = "dataworkspace.apps.api_v1.accounts.views.UserCursorPagination.page_size"

    def expected_response(self, user):
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "user_permissions_subset": {
                "develop_visualisations": False,
                "access_appstream": False,
                "access_quicksight": False,
                "start_all_applications": False,
            },
            "user_sso": str(user.profile.sso_id),
            "date_joined": "2022-01-01T10:02:03Z",
        }

    @freeze_time("2022-01-01 10:02:03")
    def test_success(self, unauthenticated_client):
        user1 = self.factory()
        user2 = self.factory()
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == [
            self.expected_response(user1),
            self.expected_response(user2),
        ]
