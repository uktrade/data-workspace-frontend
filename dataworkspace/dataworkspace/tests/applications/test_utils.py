import botocore
import mock
import pytest
import redis
from django.core.cache import cache

from dataworkspace.apps.applications.utils import (
    delete_unused_datasets_users,
    sync_quicksight_permissions,
)
from dataworkspace.tests.factories import (
    UserFactory,
    MasterDataSetFactory,
    SourceTableFactory,
)


class TestDeleteUnusedDatasetsUsers:
    def setup_method(self):
        print('setup')
        self.lock = cache.lock("delete_unused_datasets_users", blocking_timeout=0)

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
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_create_new_data_source(self, mock_cache, mock_boto3_client):
        # Arrange
        UserFactory.create(username='fake@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.list_users.return_value = {
            "UserList": [{"Arn": "Arn", "Email": "fake@email.com", "Role": "AUTHOR"}]
        }
        mock_data_client = mock.Mock()
        mock_sts_client = mock.Mock()
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]

        # Act
        sync_quicksight_permissions()

        # Assert
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
                    'CredentialPair': {
                        'Username': 'user_fake_email_com_quicksight',
                        'Password': mock.ANY,
                    }
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
    @mock.patch('dataworkspace.apps.applications.utils.boto3.client')
    @mock.patch('dataworkspace.apps.applications.utils.cache')
    def test_update_existing_data_source(self, mock_cache, mock_boto3_client):
        # Arrange
        UserFactory.create(username='fake@email.com')
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.list_users.return_value = {
            "UserList": [{"Arn": "Arn", "Email": "fake@email.com", "Role": "AUTHOR"}]
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
        mock_user_client.foo = 1
        mock_data_client.foo = 2
        mock_sts_client.foo = 3
        mock_boto3_client.side_effect = [
            mock_user_client,
            mock_data_client,
            mock_sts_client,
        ]

        # Act
        sync_quicksight_permissions()

        # Assert
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
                    'CredentialPair': {
                        'Username': 'user_fake_email_com_quicksight',
                        'Password': mock.ANY,
                    }
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
                    'CredentialPair': {
                        'Username': 'user_fake_email_com_quicksight',
                        'Password': mock.ANY,
                    }
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
