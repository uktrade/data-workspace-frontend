# pylint: disable=unspecified-encoding
import datetime
import json
import os
import random
import string

import botocore
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from waffle.testutils import override_switch
import mock
import pytest
import redis

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import (
    _do_sync_tool_query_logs,
    delete_unused_datasets_users,
    _do_create_tools_access_iam_role,
    _do_sync_activity_stream_sso_users,
    long_running_query_alert,
    sync_quicksight_permissions,
)
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import ToolQueryAuditLog, ToolQueryAuditLogTable
from dataworkspace.tests import factories

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
    @mock.patch("dataworkspace.apps.applications.utils._do_delete_unused_datasets_users")
    def test_dies_immediately_if_already_locked(self, do_delete_mock):
        do_delete_mock.side_effect = Exception("I will be raised if the lock is available")

        # Make sure we actually acquire the lock, else the test is flawed
        assert self.lock.acquire() is True
        delete_unused_datasets_users()
        self.lock.release()

        with pytest.raises(Exception) as e:
            delete_unused_datasets_users()

        assert e.value is do_delete_mock.side_effect


class TestSyncQuickSightPermissions:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.core.utils.new_private_database_credentials")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.applications.utils.cache")
    def test_create_new_data_source(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        UserFactory.create(username="fake@email.com")
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
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
                Namespace="default",
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName="user/fake@email.com",
                Email="fake@email.com",
            )
        ]
        assert mock_data_client.create_data_source.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId=mock.ANY,
                Name=mock.ANY,
                DataSourceParameters={
                    "AuroraPostgreSqlParameters": {
                        "Host": mock.ANY,
                        "Port": mock.ANY,
                        "Database": mock.ANY,
                    }
                },
                Credentials={"CredentialPair": {"Username": mock.ANY, "Password": mock.ANY}},
                VpcConnectionProperties={"VpcConnectionArn": mock.ANY},
                Type="AURORA_POSTGRESQL",
                Permissions=[
                    {
                        "Principal": "Arn",
                        "Actions": [
                            "quicksight:DescribeDataSource",
                            "quicksight:DescribeDataSourcePermissions",
                            "quicksight:PassDataSource",
                        ],
                    }
                ],
            )
        ]
        assert mock_data_client.update_data_source.call_args_list == []
        assert sorted(
            mock_data_client.delete_data_source.call_args_list,
            key=lambda x: x.kwargs["DataSourceId"],
        ) == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId="data-workspace-dev-my_database-88f3887d",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId="data-workspace-dev-test_external_db2-88f3887d",
            ),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.core.utils.new_private_database_credentials")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.applications.utils.cache")
    def test_list_user_pagination(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        UserFactory.create(username="fake@email.com")
        UserFactory.create(username="fake2@email.com")
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
            )
        )

        mock_user_client = mock.Mock()
        mock_user_client.list_users.side_effect = [
            {
                "UserList": [
                    {
                        "Arn": "Arn",
                        "Email": "fake@email.com",
                        "Role": "AUTHOR",
                        "UserName": "user/fake@email.com",
                    }
                ],
                "NextToken": "foo",
            },
            {
                "UserList": [
                    {
                        "Arn": "Arn2",
                        "Email": "fake2@email.com",
                        "Role": "AUTHOR",
                        "UserName": "user/fake2@email.com",
                    }
                ]
            },
        ]
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
                Namespace="default",
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName="user/fake@email.com",
                Email="fake@email.com",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace="default",
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName="user/fake2@email.com",
                Email="fake2@email.com",
            ),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.core.utils.new_private_database_credentials")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.applications.utils.cache")
    def test_update_existing_data_source(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        UserFactory.create(username="fake@email.com")
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
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
                "CreateDataSource",
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
                Namespace="default",
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName="user/fake@email.com",
                Email="fake@email.com",
            )
        ]
        assert mock_data_client.create_data_source.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId=mock.ANY,
                Name=mock.ANY,
                DataSourceParameters={
                    "AuroraPostgreSqlParameters": {
                        "Host": mock.ANY,
                        "Port": mock.ANY,
                        "Database": mock.ANY,
                    }
                },
                Credentials={"CredentialPair": {"Username": mock.ANY, "Password": mock.ANY}},
                VpcConnectionProperties={"VpcConnectionArn": mock.ANY},
                Type="AURORA_POSTGRESQL",
                Permissions=[
                    {
                        "Principal": "Arn",
                        "Actions": [
                            "quicksight:DescribeDataSource",
                            "quicksight:DescribeDataSourcePermissions",
                            "quicksight:PassDataSource",
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
                    "AuroraPostgreSqlParameters": {
                        "Host": mock.ANY,
                        "Port": mock.ANY,
                        "Database": mock.ANY,
                    }
                },
                Credentials={"CredentialPair": {"Username": mock.ANY, "Password": mock.ANY}},
                VpcConnectionProperties={"VpcConnectionArn": mock.ANY},
            )
        ]
        assert sorted(
            mock_data_client.delete_data_source.call_args_list,
            key=lambda x: x.kwargs["DataSourceId"],
        ) == [
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId="data-workspace-dev-my_database-88f3887d",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                DataSourceId="data-workspace-dev-test_external_db2-88f3887d",
            ),
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.core.utils.new_private_database_credentials")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.applications.utils.cache")
    def test_missing_user_handled_gracefully(self, mock_cache, mock_boto3_client, mock_creds):
        # Arrange
        user = UserFactory.create(username="fake@email.com")
        user2 = UserFactory.create(username="fake2@email.com")
        SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
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
                "DescribeUser",
            ),
            {
                "User": {
                    "Arn": "Arn",
                    "Email": "fake2@email.com",
                    "Role": "ADMIN",
                    "UserName": "user/fake2@email.com",
                }
            },
            botocore.exceptions.ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Hold up"}},
                "DescribeUser",
            ),
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
                Namespace="default",
                Role="ADMIN",
                UnapplyCustomPermissions=True,
                UserName="user/fake2@email.com",
                Email="fake2@email.com",
            )
        ]
        assert mock_user_client.describe_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace="default",
                UserName=f"quicksight_federation/{user.profile.sso_id}",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace="default",
                UserName=f"quicksight_federation/{user2.profile.sso_id}",
            ),
        ]
        assert len(mock_data_client.create_data_source.call_args_list) == 1
        assert len(mock_data_client.update_data_source.call_args_list) == 0


class TestSyncActivityStreamSSOUsers:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(ACTIVITY_STREAM_BASE_URL="http://activity.stream")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_calls_activity_stream(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.return_value = empty_result

        _do_sync_activity_stream_sso_users()

        assert mock_hawk_request.call_args_list == [
            mock.call(
                "GET",
                "http://activity.stream/v3/activities/_search",
                mock.ANY,
            )
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(ACTIVITY_STREAM_BASE_URL="http://activity.stream")
    def test_sync_first_time(self, mock_hawk_request):
        cache.delete("activity_stream_sync_last_published")
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [empty_result]

        _do_sync_activity_stream_sso_users()

        assert mock_hawk_request.call_args_list == [
            mock.call(
                "GET",
                "http://activity.stream/v3/activities/_search",
                json.dumps(
                    {
                        "size": 1000,
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"object.type": "dit:StaffSSO:User"}},
                                    {"range": {"published": {"gte": "1969-12-31T23:59:50"}}},
                                ]
                            }
                        },
                        "sort": [{"published": "asc"}, {"id": "asc"}],
                    }
                ),
            )
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(ACTIVITY_STREAM_BASE_URL="http://activity.stream")
    def test_sync_with_cache_set(self, mock_hawk_request):
        cache.set("activity_stream_sync_last_published", datetime.datetime(2020, 1, 1, 12))
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.return_value = empty_result

        _do_sync_activity_stream_sso_users()

        assert mock_hawk_request.call_args_list == [
            mock.call(
                "GET",
                "http://activity.stream/v3/activities/_search",
                json.dumps(
                    {
                        "size": 1000,
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"object.type": "dit:StaffSSO:User"}},
                                    {"range": {"published": {"gte": "2020-01-01T11:59:50"}}},
                                ]
                            }
                        },
                        "sort": [{"published": "asc"}, {"id": "asc"}],
                    }
                ),
            )
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(ACTIVITY_STREAM_BASE_URL="http://activity.stream")
    def test_sync_pagination(self, mock_hawk_request):
        cache.delete("activity_stream_sync_last_published")
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        assert mock_hawk_request.call_args_list == [
            mock.call(
                "GET",
                "http://activity.stream/v3/activities/_search",
                json.dumps(
                    {
                        "size": 1000,
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"object.type": "dit:StaffSSO:User"}},
                                    {"range": {"published": {"gte": "1969-12-31T23:59:50"}}},
                                ]
                            }
                        },
                        "sort": [{"published": "asc"}, {"id": "asc"}],
                    }
                ),
            ),
            mock.call(
                "GET",
                "http://activity.stream/v3/activities/_search",
                json.dumps(
                    {
                        "size": 1000,
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"object.type": "dit:StaffSSO:User"}},
                                    {"range": {"published": {"gte": "1969-12-31T23:59:50"}}},
                                ]
                            }
                        },
                        "sort": [{"published": "asc"}, {"id": "asc"}],
                        "search_after": [
                            1000000000000,
                            "dit:StaffSSO:User:00000000-0000-0000-0000-000000000000:Update",
                        ],
                    }
                ),
            ),
        ]

        assert cache.get("activity_stream_sync_last_published") == datetime.datetime(
            2020, 1, 1, 12
        )

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_creates_user(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert str(all_users[0].profile.sso_id) == "00000000-0000-0000-0000-000000000000"
        assert all_users[0].email == "john.smith@trade.gov.uk"
        assert all_users[0].username == "john.smith@trade.gov.uk"
        assert all_users[0].first_name == "John"
        assert all_users[0].last_name == "Smith"

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_updates_existing_users_sso_id(self, mock_hawk_request):
        user = UserFactory.create(email="john.smith@trade.gov.uk")
        # set the sso id to something different to what the activity stream
        # will return to test that it gets updated
        user.profile.sso_id = "00000000-0000-0000-0000-111111111111"
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert str(all_users[0].profile.sso_id) == "00000000-0000-0000-0000-000000000000"

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_updates_existing_users_email(self, mock_hawk_request):
        # set the email to something different to what the activity stream
        # will return to test that it gets updated
        user = UserFactory.create(email="john.smith@gmail.com")
        user.profile.sso_id = "00000000-0000-0000-0000-000000000000"
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert str(all_users[0].email) == "john.smith@trade.gov.uk"

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_updates_existing_users_sso_id_and_email(self, mock_hawk_request):
        # set the sso id to something different to what the activity stream
        # will return and set the email to the third email in the list that
        # the activity stream will return to test that it is able to look up
        # the user and update both their email and sso id
        user = UserFactory.create(email="john@trade.gov.uk")
        user.profile.sso_id = "00000000-0000-0000-0000-111111111111"
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith_multiple_emails.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert str(all_users[0].profile.sso_id) == "00000000-0000-0000-0000-000000000000"
        assert str(all_users[0].email) == "john.smith@digital.trade.gov.uk"

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role_task")
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_creates_role_if_user_can_access_tools(
        self, mock_hawk_request, create_tools_access_iam_role_task
    ):
        can_access_tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = UserFactory.create(email="john.smith@trade.gov.uk")
        user.profile.sso_id = "00000000-0000-0000-0000-000000000000"
        user.save()
        user.user_permissions.add(can_access_tools_permission)

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert create_tools_access_iam_role_task.delay.call_args_list == [
            mock.call(
                user.id,
            )
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role_task")
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_doesnt_create_role_if_user_cant_access_tools(
        self, mock_hawk_request, create_tools_access_iam_role_task
    ):
        user = UserFactory.create(email="john.smith@trade.gov.uk")
        user.profile.sso_id = "00000000-0000-0000-0000-000000000000"
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert not create_tools_access_iam_role_task.delay.called

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role_task")
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_doesnt_create_role_if_user_already_has_role(
        self, mock_hawk_request, create_tools_access_iam_role_task
    ):
        can_access_tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = UserFactory.create(email="john.smith@trade.gov.uk")
        user.user_permissions.add(can_access_tools_permission)
        user.profile.sso_id = "00000000-0000-0000-0000-000000000000"
        user.profile.tools_access_role_arn = "some-arn"
        user.save()

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_john_smith.json",
            ),
            "r",
        ) as file:
            user_john_smith = (200, file.read())

        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_empty.json",
            ),
            "r",
        ) as file:
            empty_result = (200, file.read())

        mock_hawk_request.side_effect = [user_john_smith, empty_result]

        _do_sync_activity_stream_sso_users()

        User = get_user_model()
        all_users = User.objects.all()

        assert len(all_users) == 1
        assert not create_tools_access_iam_role_task.delay.called

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_hawk_request_fails(self, mock_hawk_request):
        mock_hawk_request.return_value = 500, "Unable to reach shard"

        with pytest.raises(Exception) as e:
            _do_sync_activity_stream_sso_users()
            assert str(e.value) == "Failed to fetch SSO users: Unable to reach shard"

        User = get_user_model()
        assert not User.objects.all()

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.hawk_request")
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_failures_in_response(self, mock_hawk_request):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "test_fixture_activity_stream_sso_failures.json",
            ),
            "r",
        ) as file:
            failure_response = (200, file.read())

        mock_hawk_request.return_value = failure_response

        with pytest.raises(Exception) as e:
            _do_sync_activity_stream_sso_users()
            assert str(e.value) == "Failed to fetch SSO users: An error occured"

        User = get_user_model()
        assert not User.objects.all()


class TestCreateToolsAccessIAMRoleTask:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role")
    def test_task_creates_iam_role(self, mock_create_tools_access_iam_role):

        user = UserFactory.create(username="john.smith@trade.gov.uk")
        user.profile.sso_id = "00000000-0000-0000-0000-000000000001"
        user.profile.home_directory_efs_access_point_id = "some-access-point-id"
        user.save()

        _do_create_tools_access_iam_role(user.id)

        assert mock_create_tools_access_iam_role.call_args_list == [
            mock.call(
                "john.smith@trade.gov.uk",
                "some-access-point-id",
            )
        ]

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role")
    @mock.patch("logging.Logger.exception")
    def test_task_fails_non_existent_user(self, mock_logger, mock_create_tools_access_iam_role):
        _do_create_tools_access_iam_role(2)
        assert mock_logger.call_args_list == [mock.call("User id %d does not exist", 2)]


class TestSyncToolQueryLogs:
    log_data = [
        # Valid user and db select statement
        '2020-12-08 18:00:00.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""SELECT * FROM dataset_test"",<not logged>",,,,,,,,,""\n',
        # Non-pgaudit log
        '2020-12-08 18:00:10.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"A random message",,,,,,,,,""\n',
        # Unrecognised user
        '2020-12-08 18:00:20.395 UTC,"unknownuser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19041,"SELECT",2020-12-08 18:18:19 UTC,9/19034,0,LOG,00000,'
        '"AUDIT: SESSION,19041,1,READ,SELECT,,,""SELECT a FROM b"",<not logged>",,,,,,,,,""\n',
        # Unrecognised db
        '2020-12-08 18:00:30.395 UTC,"auser","unknowndb",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19041,"SELECT",2020-12-08 18:18:19 UTC,9/19034,0,LOG,00000,'
        '"AUDIT: SESSION,19041,1,READ,SELECT,,,""SELECT c FROM d"",<not logged>",,,,,,,,,""\n',
        # Valid user and db insert statement
        '2020-12-08 18:00:40.400 UTC,"auser","test_datasets",114,"172.19.0.5:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""INSERT INTO dataset_test VALUES(1);"",<not logged>"'
        ',,,,,,,,,""\n',
        # Timestamp out of range
        '2020-12-08 17:00:00.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""INSERT INTO dataset_test VALUES(2);"",<not logged>"'
        ',,,,,,,,,""\n',
        # No timestamp
        "An exception occurred...\n",
        # Duplicate record
        '2020-12-08 18:00:00.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""SELECT * FROM dataset_test"",<not logged>",,,,,,,,,""\n',
        # Ignored statement
        '2020-12-08 19:00:00.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""select CAST(id as VARCHAR(50)) as col1 from a"",'
        '<not logged>",,,,,,,,,""\n',
        # > 1 million characters
        '2020-12-08 20:00:00.400 UTC,"auser","test_datasets",114,"172.19.0.4:53462",'
        '5fcfc36b.72,19047,"SELECT",2020-12-08 18:18:19 UTC,9/19040,0,LOG,00000,'
        '"AUDIT: SESSION,19047,1,READ,SELECT,,,""'
        f'{"".join(random.choices(string.ascii_letters, k=1500000))}"",<not logged>",,,,,,,,,""\n',
    ]

    @pytest.mark.django_db(transaction=True)
    @freeze_time("2020-12-08 18:04:00")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @override_settings(
        PGAUDIT_LOG_TYPE="rds",
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
    )
    def test_rds_sync(self, mock_client, dataset_db):
        cache.delete("q" "uery_tool_logs_last_run")
        log_count = ToolQueryAuditLog.objects.count()
        table_count = ToolQueryAuditLogTable.objects.count()
        factories.DatabaseFactory(memorable_name="my_database")
        factories.DatabaseUserFactory.create(username="auser")
        factories.SourceTableFactory.create(schema="public", table="test_dataset")
        mock_client.return_value.describe_db_log_files.return_value = {
            "DescribeDBLogFiles": [
                {"LogFileName": "/file/1.csv"},
                {"LogFileName": "/file/2.csv"},
            ]
        }
        mock_client.return_value.download_db_log_file_portion.side_effect = [
            {
                "Marker": "1",
                "AdditionalDataPending": True,
                "LogFileData": (
                    # Valid user and db select statement
                    self.log_data[0]
                    # Non-pgaudit log
                    + self.log_data[1]
                ),
            },
            {
                "Marker": None,
                "AdditionalDataPending": False,
                "LogFileData": (
                    # Unrecognised user
                    self.log_data[2]
                    # Unrecognised database
                    + self.log_data[3]
                ),
            },
            {
                "Marker": None,
                "AdditionalDataPending": False,
                "LogFileData": (
                    # Valid username and db insert statement
                    self.log_data[4]
                    # Timestamp out of range
                    + self.log_data[5]
                    # No timestamp
                    + self.log_data[6]
                    # Duplicate log entry
                    + self.log_data[7]
                ),
            },
        ]
        _do_sync_tool_query_logs()
        queries = ToolQueryAuditLog.objects.all()
        tables = ToolQueryAuditLogTable.objects.all()
        assert queries.count() == log_count + 2
        assert tables.count() == table_count + 1
        assert list(queries)[-2].query_sql == "SELECT * FROM dataset_test"
        assert list(queries)[-2].connection_from == "172.19.0.4"
        assert list(queries)[-1].query_sql == "INSERT INTO dataset_test VALUES(1);"
        assert list(queries)[-1].connection_from == "172.19.0.5"

    @pytest.mark.django_db(transaction=True)
    @freeze_time("2020-12-08 18:04:00")
    @mock.patch("dataworkspace.apps.applications.utils.os")
    @mock.patch("builtins.open", mock.mock_open(read_data="".join(log_data)))
    @override_settings(
        PGAUDIT_LOG_TYPE="docker",
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
    )
    def test_docker_sync(self, mock_os, dataset_db):
        cache.delete("query_tool_logs_last_run")
        table_count = ToolQueryAuditLogTable.objects.count()
        log_count = ToolQueryAuditLog.objects.count()
        factories.DatabaseFactory(memorable_name="my_database")
        factories.DatabaseUserFactory.create(username="auser")
        factories.SourceTableFactory.create(schema="public", table="test_dataset")
        mock_os.listdir.return_value = [
            "file1.csv",
            "file2.log",
        ]
        mock_os.path.getmtime.return_value = datetime.datetime.now().timestamp()
        _do_sync_tool_query_logs()
        queries = ToolQueryAuditLog.objects.all()
        tables = ToolQueryAuditLogTable.objects.all()
        assert queries.count() == log_count + 2
        assert tables.count() == table_count + 1
        assert list(queries)[-2].query_sql == "SELECT * FROM dataset_test"
        assert list(queries)[-1].query_sql == "INSERT INTO dataset_test VALUES(1);"


class TestLongRunningQueryAlerts:
    @pytest.mark.django_db
    @override_switch("enable_long_running_query_alerts", active=True)
    @mock.patch("dataworkspace.apps.applications.utils.connections")
    @mock.patch("dataworkspace.apps.applications.utils._send_slack_message")
    def test_no_long_running_queries(self, mock_send_slack_message, mock_connections):
        mock_cursor = mock.Mock()
        mock_cursor.fetchone.return_value = [0]
        mock_connection = mock.Mock()
        mock_cursor_ctx_manager = mock.MagicMock()
        mock_cursor_ctx_manager.__enter__.return_value = mock_cursor
        mock_connection.cursor.return_value = mock_cursor_ctx_manager
        mock_connections.__getitem__.return_value = mock_connection
        long_running_query_alert()
        mock_send_slack_message.assert_not_called()

    @pytest.mark.django_db
    @override_switch("enable_long_running_query_alerts", active=True)
    @override_settings(SLACK_SENTRY_CHANNEL_WEBHOOK="http://test.com")
    @mock.patch("dataworkspace.apps.applications.utils.connections")
    @mock.patch("dataworkspace.apps.applications.utils._send_slack_message")
    def test_long_running_queries(self, mock_send_slack_message, mock_connections):
        mock_cursor = mock.Mock()
        mock_cursor.fetchone.return_value = [1]
        mock_connection = mock.Mock()
        mock_cursor_ctx_manager = mock.MagicMock()
        mock_cursor_ctx_manager.__enter__.return_value = mock_cursor
        mock_connection.cursor.return_value = mock_cursor_ctx_manager
        mock_connections.__getitem__.return_value = mock_connection
        long_running_query_alert()
        mock_send_slack_message.assert_called_once_with(
            ":rotating_light: Found 1 SQL query running for longer than 15 minutes "
            "on the datasets db."
        )
