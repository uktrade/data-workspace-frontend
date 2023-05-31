from unittest import mock
import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.factories import UserFactory
from dataworkspace.tests.api_v1.base import BaseAPIViewTest
from dataworkspace.tests.core.factories import TeamFactory


@pytest.mark.django_db
class TestGetSupersetCredentialsAPIView:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.api_v1.core.views.cache")
    @mock.patch("dataworkspace.apps.api_v1.core.views.source_tables_for_user")
    @mock.patch("dataworkspace.apps.api_v1.core.views.new_private_database_credentials")
    def test_first_time_user_with_tools_access_succeeds(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
        dataset_db,
    ):
        credentials = [{"db_user": "foo", "db_password": "bar"}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()
        tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(tools_permission)

        headers = {
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_HOST": f"superset-edit.{settings.APPLICATION_ROOT_DOMAIN}",
        }
        response = unauthenticated_client.get(
            reverse("api-v1:core:get-superset-role-credentials"), **headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["credentials"] == credentials[0]
        assert response.json()["dashboards"] == []

        assert mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call("superset_credentials_version", 1, nx=True, timeout=None),
            mock.call(
                f"superset_credentials_1_edit_{user.username}",
                {"credentials": credentials[0], "dashboards": []},
                timeout=mock.ANY,
            ),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.api_v1.core.views.cache")
    @mock.patch("dataworkspace.apps.api_v1.core.views.source_tables_for_user")
    @mock.patch("dataworkspace.apps.api_v1.core.views.new_private_database_credentials")
    def test_first_time_user_without_tools_access_fails(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
        dataset_db,
    ):
        credentials = [{"db_user": "foo", "db_password": "bar"}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_HOST": f"superset-edit.{settings.APPLICATION_ROOT_DOMAIN}",
        }
        response = unauthenticated_client.get(
            reverse("api-v1:core:get-superset-role-credentials"), **header
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call("superset_credentials_version", 1, nx=True, timeout=None),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.api_v1.core.views.cache")
    @mock.patch("dataworkspace.apps.api_v1.core.views.source_tables_for_user")
    @mock.patch("dataworkspace.apps.api_v1.core.views.new_private_database_credentials")
    def test_returning_user_succeeds(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
        dataset_db,
    ):
        credentials = [{"db_user": "foo", "db_password": "bar"}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            {
                "credentials": credentials[0],
                "dashboards": [],
            },  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_HOST": f"superset-edit.{settings.APPLICATION_ROOT_DOMAIN}",
        }
        response = unauthenticated_client.get(
            reverse("api-v1:core:get-superset-role-credentials"), **header
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["credentials"] == credentials[0]
        assert response.json()["dashboards"] == []

        assert not mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call("superset_credentials_version", 1, nx=True, timeout=None),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.api_v1.core.views.cache")
    def test_public_user_gets_db_access(self, mock_cache, unauthenticated_client, dataset_db):
        visualisation = factories.VisualisationLinkFactory(
            visualisation_type="SUPERSET",
            visualisation_catalogue_item__user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )
        credentials = {
            "memorable_name": "my_database",
            "db_name": "test_datasets",
            "db_host": "data-workspace-postgres",
            "db_port": "5432",
            "db_user": "postgres",
            "db_password": "postgres",
        }
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]

        user = factories.UserFactory()
        tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(tools_permission)

        headers = {
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_HOST": f"superset.{settings.APPLICATION_ROOT_DOMAIN}",
        }
        response = unauthenticated_client.get(
            reverse("api-v1:core:get-superset-role-credentials"), **headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["credentials"] == credentials
        assert response.json()["dashboards"] == [visualisation.identifier]

        assert mock_cache.set.call_args_list == [
            mock.call("superset_credentials_version", 1, nx=True, timeout=None),
            mock.call(
                f"superset_credentials_1_view_{user.username}",
                {"credentials": credentials, "dashboards": [visualisation.identifier]},
                timeout=mock.ANY,
            ),
        ]


class TestTeamsAPIView(BaseAPIViewTest):
    url = reverse("api-v1:core:teams")
    pagination_class = "dataworkspace.apps.api_v1.core.views.PageNumberPagination.page_size"
    factory = TeamFactory

    def test_success(self, unauthenticated_client):
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        team1 = TeamFactory.create()
        team2 = TeamFactory.create()
        team1.member.add(user1.id)
        team1.member.add(user2.id)
        team2.member.add(user3.id)
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == [
            {
                "id": str(team1.id),
                "name": team1.name,
                "schema_name": team1.schema_name,
                "members": [
                    user1.id,
                    user2.id,
                ],
            },
            {
                "id": str(team2.id),
                "name": team2.name,
                "schema_name": team2.schema_name,
                "members": [
                    user3.id,
                ],
            },
        ]
