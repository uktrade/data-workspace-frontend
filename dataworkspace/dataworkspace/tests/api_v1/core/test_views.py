from unittest import mock
import pytest
from django.conf import settings
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
        dataset_db,
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

        headers = {
            'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id,
            'HTTP_HOST': f'superset-edit.{settings.APPLICATION_ROOT_DOMAIN}',
        }
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['credentials'] == credentials[0]
        assert response.json()['dashboards'] == []

        assert mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call('superset_credentials_version', 1, nx=True, timeout=None),
            mock.call(
                f'superset_credentials_1_edit_{user.profile.sso_id}',
                {
                    'credentials': credentials[0],
                    'dashboards': [],
                    'impersonation_sso_headers': None,
                },
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
        dataset_db,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {
            'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id,
            'HTTP_HOST': f'superset-edit.{settings.APPLICATION_ROOT_DOMAIN}',
        }
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call('superset_credentials_version', 1, nx=True, timeout=None),
        ]

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
        dataset_db,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            {
                'credentials': credentials[0],
                'dashboards': [],
            },  # cache.get(cache_key, None)
        ]
        mock_new_credentials.return_value = credentials

        user = factories.UserFactory()

        header = {
            'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id,
            'HTTP_HOST': f'superset-edit.{settings.APPLICATION_ROOT_DOMAIN}',
        }
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['credentials'] == credentials[0]
        assert response.json()['dashboards'] == []

        assert not mock_new_credentials.called
        assert mock_cache.set.call_args_list == [
            mock.call('superset_credentials_version', 1, nx=True, timeout=None),
        ]

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.api_v1.core.views.new_private_database_credentials')
    def test_impersonating_user_succeeds(
        self,
        mock_new_credentials,
        unauthenticated_client,
        dataset_db,
        admin_user,
        user,
    ):
        credentials = [{'db_user': 'foo', 'db_password': 'bar'}]
        mock_new_credentials.return_value = credentials

        tools_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(tools_permission)

        header = {
            'HTTP_SSO_PROFILE_USER_ID': admin_user.profile.sso_id,
            'HTTP_HOST': f'superset-edit.{settings.APPLICATION_ROOT_DOMAIN}',
        }

        session = unauthenticated_client.session
        session['impersonated_user'] = user
        session.save()
        unauthenticated_client.cookies[
            settings.SESSION_COOKIE_NAME
        ] = session.session_key
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **header
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['credentials'] == credentials[0]
        assert response.json()['dashboards'] == []
        assert response.json()['impersonation_sso_headers'] == [
            ['sso-profile-email', user.email],
            ['sso-profile-contact-email', ''],
            ['sso-profile-related-emails', ''],
            ['sso-profile-user-id', user.id],
            ['sso-profile-first-name', user.first_name],
            ['sso-profile-last-name', user.last_name],
        ]

        assert mock_new_credentials.called

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.api_v1.core.views.cache')
    def test_public_user_gets_db_access(
        self, mock_cache, unauthenticated_client, dataset_db
    ):
        visualisation = factories.VisualisationLinkFactory(
            visualisation_type='SUPERSET',
            visualisation_catalogue_item__user_access_type='REQUIRES_AUTHENTICATION',
        )
        credentials = {
            'memorable_name': 'my_database',
            'db_name': 'test_datasets',
            'db_host': 'data-workspace-postgres',
            'db_port': '5432',
            'db_user': 'postgres',
            'db_password': 'postgres',
        }
        mock_cache.get.side_effect = [
            1,  # cache.get(credentials_version_key, None)
            None,  # cache.get(cache_key, None)
        ]

        user = factories.UserFactory()
        tools_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(tools_permission)

        headers = {
            'HTTP_SSO_PROFILE_USER_ID': user.profile.sso_id,
            'HTTP_HOST': f'superset.{settings.APPLICATION_ROOT_DOMAIN}',
        }
        response = unauthenticated_client.get(
            reverse('api-v1:core:get-superset-role-credentials'), **headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['credentials'] == credentials
        assert response.json()['dashboards'] == [visualisation.identifier]

        assert mock_cache.set.call_args_list == [
            mock.call('superset_credentials_version', 1, nx=True, timeout=None),
            mock.call(
                f'superset_credentials_1_view_{user.profile.sso_id}',
                {
                    'credentials': credentials,
                    'dashboards': [visualisation.identifier],
                    'impersonation_sso_headers': None,
                },
                timeout=mock.ANY,
            ),
        ]
