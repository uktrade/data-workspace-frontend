from unittest import mock
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.tests import factories


@pytest.mark.django_db
class TestGetSupersetCredentialsAPIView:
    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.api_v1.core.views.cache')
    @mock.patch('dataworkspace.apps.api_v1.core.views.source_tables_for_user')
    @mock.patch('dataworkspace.apps.api_v1.core.views.new_private_database_credentials')
    def test_first_time_user_with_tools_access_succeeds(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()
        tools_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(tools_permission)

        header = {'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id}
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == credentials[0]

        assert mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call(
                f'superset_credentials_1_{user.profile.sso_id}',
                credentials,
                timeout=mock.ANY,
            ),
        ]

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.api_v1.core.views.cache')
    @mock.patch('dataworkspace.apps.api_v1.core.views.source_tables_for_user')
    @mock.patch('dataworkspace.apps.api_v1.core.views.new_private_database_credentials')
    def test_first_time_user_without_tools_access_fails(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id}
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not mock_new_credentials.called
        assert not mock_cache.set.called

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.api_v1.core.views.cache')
    @mock.patch('dataworkspace.apps.api_v1.core.views.source_tables_for_user')
    @mock.patch('dataworkspace.apps.api_v1.core.views.new_private_database_credentials')
    def test_returning_user_succeeds(
        self,
        mock_new_credentials,
        mock_source_tables,
        mock_cache,
        unauthenticated_client,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            credentials,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id}
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == credentials[0]

        assert not mock_new_credentials.called
        assert not mock_cache.set.called
