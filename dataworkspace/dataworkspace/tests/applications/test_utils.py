import json
import os

import botocore
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
import mock
import pytest
import redis

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import (
    delete_unused_datasets_users,
    sync_activity_stream_sso_users,
    sync_quicksight_permissions,
)

from dataworkspace.tests.factories import (
    UserFactory,
    MasterDataSetFactory,
    SourceTableFactory,
)


class TestDeleteUnusedDatasetsUsers:
    def setup_method(self):
        self.lock = cache.lock(  # pylint: disable=attribute-defined-outside-init
            "delete_unused_datasets_users", blocking_timeout=0
        )

    def teardown_method(self):
        try:
            self.lock.release()
        except redis.exceptions.LockError:
            pass

    @pytest.mark.timeout(2)
    @mock.patch(
        'dataworkspace.apps.applications.utils._do_delete_unused_datasets_users'
    )
    def test_dies_immediately_if_already_locked(self, do_delete_mock):
        do_delete_mock.side_effect = Exception(
            "I will be raised if the lock is available"
        )

        # Make sure we actually acquire the lock, else the test is flawed
        assert self.lock.acquire() is True
        delete_unused_datasets_users()
        self.lock.release()

        with pytest.raises(Exception) as e:
            delete_unused_datasets_users()

        assert e.value is do_delete_mock.side_effect


class TestSyncQuickSightPermissions:
    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.core.utils.new_private_database_credentials')
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_create_new_data_source(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        UserFactory.create(username='fake@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.list_users.return_value = {
            "UserList": [
                {
                    "Arn": "Arn",
                    "Email": "fake@email.com",
                    "Role": "AUTHOR",
                    "UserName": "user/fake@email.com",
                }
            ]
        }
        mock_data_client = mock.Mock()
        mock_sts_client = mock.Mock()
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]
        mock_creds.return_value = [mock.Mock()]

        # Act
        sync_quicksight_permissions()

        # Assert
        assert mock_user_client.update_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                Role='AUTHOR',
                CustomPermissionsName='author-custom-permissions',
                UserName='user/fake@email.com',
                Email='fake@email.com',
            )
        ]
        assert mock_data_client.create_data_source.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId=mock.ANY,
                Name=mock.ANY,
                DataSourceParameters={
                    'AuroraPostgreSqlParameters': {
                        'Host': mock.ANY,
                        'Port': mock.ANY,
                        'Database': mock.ANY,
                    }
                },
                Credentials={
                    'CredentialPair': {'Username': mock.ANY, 'Password': mock.ANY}
                },
                VpcConnectionProperties={'VpcConnectionArn': mock.ANY},
                Type='AURORA_POSTGRESQL',
                Permissions=[
                    {
                        'Principal': 'Arn',
                        'Actions': [
                            'quicksight:DescribeDataSource',
                            'quicksight:DescribeDataSourcePermissions',
                            'quicksight:PassDataSource',
                        ],
                    }
                ],
            )
        ]
        assert mock_data_client.update_data_source.call_args_list == []
        assert sorted(
            mock_data_client.delete_data_source.call_args_list,
            key=lambda x: x.kwargs['DataSourceId'],
        ) == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId='data-workspace-dev-my_database-88f3887d',
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId='data-workspace-dev-test_external_db2-88f3887d',
            ),
        ]

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.core.utils.new_private_database_credentials')
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_update_existing_data_source(
        self, mock_cache, mock_boto3_client, mock_creds
    ):
        # Arrange
        UserFactory.create(username='fake@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.list_users.return_value = {
            "UserList": [
                {
                    "Arn": "Arn",
                    "Email": "fake@email.com",
                    "Role": "AUTHOR",
                    "UserName": "user/fake@email.com",
                }
            ]
        }
        mock_data_client = mock.Mock()
        mock_data_client.create_data_source.side_effect = [
            botocore.exceptions.ClientError(
                {
                    "Error": {
                        "Code": "ResourceExistsException",
                        "Message": "Data source already exists",
                    }
                },
                'CreateDataSource',
            )
        ]
        mock_sts_client = mock.Mock()
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]

        # Act
        sync_quicksight_permissions()

        # Assert
        assert mock_user_client.update_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                Role='AUTHOR',
                CustomPermissionsName='author-custom-permissions',
                UserName='user/fake@email.com',
                Email='fake@email.com',
            )
        ]
        assert mock_data_client.create_data_source.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId=mock.ANY,
                Name=mock.ANY,
                DataSourceParameters={
                    'AuroraPostgreSqlParameters': {
                        'Host': mock.ANY,
                        'Port': mock.ANY,
                        'Database': mock.ANY,
                    }
                },
                Credentials={
                    'CredentialPair': {'Username': mock.ANY, 'Password': mock.ANY}
                },
                VpcConnectionProperties={'VpcConnectionArn': mock.ANY},
                Type='AURORA_POSTGRESQL',
                Permissions=[
                    {
                        'Principal': 'Arn',
                        'Actions': [
                            'quicksight:DescribeDataSource',
                            'quicksight:DescribeDataSourcePermissions',
                            'quicksight:PassDataSource',
                        ],
                    }
                ],
            )
        ]
        assert mock_data_client.update_data_source.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId=mock.ANY,
                Name=mock.ANY,
                DataSourceParameters={
                    'AuroraPostgreSqlParameters': {
                        'Host': mock.ANY,
                        'Port': mock.ANY,
                        'Database': mock.ANY,
                    }
                },
                Credentials={
                    'CredentialPair': {'Username': mock.ANY, 'Password': mock.ANY}
                },
                VpcConnectionProperties={'VpcConnectionArn': mock.ANY},
            )
        ]
        assert sorted(
            mock_data_client.delete_data_source.call_args_list,
            key=lambda x: x.kwargs['DataSourceId'],
        ) == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId='data-workspace-dev-my_database-88f3887d',
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId='data-workspace-dev-test_external_db2-88f3887d',
            ),
        ]

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.core.utils.new_private_database_credentials')
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_missing_user_handled_gracefully(
        self, mock_cache, mock_boto3_client, mock_creds
    ):
        # Arrange
        user = UserFactory.create(username='fake@email.com')
        user2 = UserFactory.create(username='fake2@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.describe_user.side_effect = [
            botocore.exceptions.ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "User not found",
                    }
                },
                'DescribeUser',
            ),
            {
                "User": {
                    "Arn": "Arn",
                    "Email": "fake2@email.com",
                    "Role": "ADMIN",
                    "UserName": "user/fake2@email.com",
                }
            },
        ]
        mock_data_client = mock.Mock()
        mock_sts_client = mock.Mock()
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]

        # Act
        sync_quicksight_permissions(
            user_sso_ids_to_update=[str(user.profile.sso_id), str(user2.profile.sso_id)]
        )

        # Assert
        assert mock_user_client.update_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                Role='ADMIN',
                UnapplyCustomPermissions=True,
                UserName='user/fake2@email.com',
                Email='fake2@email.com',
            )
        ]
        assert mock_user_client.describe_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                UserName=f'quicksight_federation/{user.profile.sso_id}',
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                UserName=f'quicksight_federation/{user2.profile.sso_id}',
            ),
        ]
        assert len(mock_data_client.create_data_source.call_args_list) == 1
        assert len(mock_data_client.update_data_source.call_args_list) == 0

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.core.utils.new_private_database_credentials')
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_poll_until_user_created(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        user = UserFactory.create(username='fake@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.describe_user.side_effect = [
            botocore.exceptions.ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "User not found",
                    }
                },
                'DescribeUser',
            ),
        ] * 10 + [
            {
                "User": {
                    "Arn": "Arn",
                    "Email": "fake@email.com",
                    "Role": "AUTHOR",
                    "UserName": "user/fake@email.com",
                }
            }
        ]
        mock_data_client = mock.Mock()
        mock_sts_client = mock.Mock()
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]

        # Act
        with mock.patch('dataworkspace.apps.applications.utils.gevent.sleep'):
            sync_quicksight_permissions(
                user_sso_ids_to_update=[str(user.profile.sso_id)],
                poll_for_user_creation=True,
            )

        # Assert
        assert mock_user_client.update_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace='default',
                Role='AUTHOR',
                CustomPermissionsName='author-custom-permissions',
                UserName='user/fake@email.com',
                Email='fake@email.com',
            )
        ]
        assert (
            mock_user_client.describe_user.call_args_list
            == [
                mock.call(
                    AwsAccountId=mock.ANY,
                    Namespace='default',
                    UserName=f'quicksight_federation/{user.profile.sso_id}',
                ),
            ]
            * 11
        )
        assert len(mock_data_client.create_data_source.call_args_list) == 1
        assert len(mock_data_client.update_data_source.call_args_list) == 0


class TestSyncActivityStreamSSOUsers:
    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    @override_settings(ACTIVITY_STREAM_BASE_URL='http://activity.stream')
    @override_settings(ACTIVITY_STREAM_HAWK_CREDENTIALS_ID='hawk_id')
    @override_settings(ACTIVITY_STREAM_HAWK_CREDENTIALS_KEY='hawk_key')
    def test_sync_calls_activity_stream(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.return_value = empty_result

        sync_activity_stream_sso_users()

        assert mock_hawk_request.call_args_list == [
            mock.call(
                'GET',
                'http://activity.stream/v3/activities/_search',
                'hawk_id',
                'hawk_key',
                mock.ANY,
            )
        ]

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    @override_settings(ACTIVITY_STREAM_BASE_URL='http://activity.stream')
    def test_sync_all_users(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_john_smith_object.json',
            ),
            'r',
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        sync_activity_stream_sso_users(all_users=True)

        assert mock_hawk_request.call_args_list == [
            mock.call(
                mock.ANY,
                'http://activity.stream/v3/objects/_search',
                mock.ANY,
                mock.ANY,
                json.dumps(
                    {
                        "query": {
                            "bool": {
                                "filter": [{"term": {"type": "dit:StaffSSO:User"}}]
                            }
                        },
                        "sort": [{"dit:StaffSSO:User:joined": "desc"}],
                    }
                ),
            ),
            mock.call(
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY,
                json.dumps(
                    {
                        "query": {
                            "bool": {
                                "filter": [{"term": {"type": "dit:StaffSSO:User"}}]
                            }
                        },
                        "sort": [{"dit:StaffSSO:User:joined": "desc"}],
                        "search_after": [1000000000000],
                    }
                ),
            ),
        ]

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert (
            str(all_users[0].profile.sso_id) == '00000000-0000-0000-0000-000000000000'
        )
        assert all_users[0].email == 'john.smith@trade.gov.uk'
        assert all_users[0].username == 'john.smith@trade.gov.uk'
        assert all_users[0].first_name == 'John'
        assert all_users[0].last_name == 'Smith'

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_with_no_results(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.return_value = empty_result

        sync_activity_stream_sso_users()

        User = get_user_model()
        assert not User.objects.all()

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    @freeze_time('2020-01-01 12:00:00')
    def test_sync_recently_published_users(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.return_value = empty_result

        sync_activity_stream_sso_users(all_users=False)

        assert mock_hawk_request.call_args_list == [
            mock.call(
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY,
                json.dumps(
                    {
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"object.type": "dit:StaffSSO:User"}},
                                    {
                                        "range": {
                                            "published": {"gte": "2020-01-01T11:59"}
                                        }
                                    },
                                ]
                            }
                        },
                        "sort": [{"published": "desc"}],
                    }
                ),
            )
        ]

        User = get_user_model()
        assert not User.objects.all()

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_updates_existing_user(self, mock_hawk_request):
        user = UserFactory.create(username='john.smith@trade.gov.uk')
        # set the sso id to something different to what the activity stream
        # will return to test that it gets updated
        user.profile.sso_id = '00000000-0000-0000-0000-111111111111'
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_john_smith_activity.json',
            ),
            'r',
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert (
            str(all_users[0].profile.sso_id) == '00000000-0000-0000-0000-000000000000'
        )

    @pytest.mark.django_db
    @mock.patch(
        'dataworkspace.apps.applications.utils.publish_to_iam_role_creation_channel'
    )
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_creates_role_if_user_can_access_tools(
        self, mock_hawk_request, publish_to_iam_role_creation_channel
    ):
        can_access_tools_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = UserFactory.create(username='john.smith@trade.gov.uk')
        user.user_permissions.add(can_access_tools_permission)

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_john_smith_activity.json',
            ),
            'r',
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert publish_to_iam_role_creation_channel.called
        assert publish_to_iam_role_creation_channel.call_args_list == [mock.call(user,)]

    @pytest.mark.django_db
    @mock.patch(
        'dataworkspace.apps.applications.utils.publish_to_iam_role_creation_channel'
    )
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_doesnt_create_role_if_user_cant_access_tools(
        self, mock_hawk_request, publish_to_iam_role_creation_channel
    ):
        UserFactory.create(username='john.smith@trade.gov.uk')

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_john_smith_activity.json',
            ),
            'r',
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert not publish_to_iam_role_creation_channel.called

    @pytest.mark.django_db
    @mock.patch(
        'dataworkspace.apps.applications.utils.publish_to_iam_role_creation_channel'
    )
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_doesnt_create_role_if_user_already_has_role(
        self, mock_hawk_request, publish_to_iam_role_creation_channel
    ):
        can_access_tools_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = UserFactory.create(username='john.smith@trade.gov.uk')
        user.user_permissions.add(can_access_tools_permission)
        user.profile.tools_access_role_arn = 'some-arn'
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_john_smith_activity.json',
            ),
            'r',
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_empty.json',
            ),
            'r',
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert not publish_to_iam_role_creation_channel.called

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_hawk_request_fails(self, mock_hawk_request):
        mock_hawk_request.return_value = 500, "Unable to reach shard"

        with pytest.raises(Exception) as e:
            sync_activity_stream_sso_users()
            assert str(e.value) == 'Failed to fetch SSO users: Unable to reach shard'

        User = get_user_model()
        assert not User.objects.all()

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.applications.utils.hawk_request')
    def test_sync_failures_in_response(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'test_fixture_activity_stream_sso_failures.json',
            ),
            'r',
        ) as file:
            failure_response = (200, file.read())

        mock_hawk_request.return_value = failure_response

        with pytest.raises(Exception) as e:
            sync_activity_stream_sso_users()
            assert str(e.value) == 'Failed to fetch SSO users: An error occured'

        User = get_user_model()
        assert not User.objects.all()
