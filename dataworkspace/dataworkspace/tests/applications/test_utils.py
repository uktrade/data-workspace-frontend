# pylint: disable=unspecified-encoding
import calendar
import datetime
import json
import random
import string
from unittest.mock import call, patch

import botocore
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import override_settings


from dateutil import parser
from dateutil.tz import tzlocal

from freezegun import freeze_time
from waffle.testutils import override_switch
import mock
import pytest
import redis

from dataworkspace.apps.accounts.models import Profile
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import (
    _do_sync_tool_query_logs,
    delete_unused_datasets_users,
    _do_create_tools_access_iam_role,
    long_running_query_alert,
    sync_quicksight_permissions,
    _do_sync_s3_sso_users,
    _process_staff_sso_file,
    _get_seen_ids_and_last_processed,
    _do_get_staff_sso_s3_object_summaries,
    remove_tools_access_for_users_with_expired_cert,
    self_certify_renewal_email_notification,
    _is_full_sync,
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
        user = UserFactory.create(username="fake@email.com")
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
                    "UserName": f"user/fake@email.com/{user.profile.sso_id}",
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
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName=f"user/fake@email.com/{user.profile.sso_id}",
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
        UserFactory.create(username="fake@email.com", email="updated@email.com")
        UserFactory.create(username="fake2@email.com", email="fake2@email.com")
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
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName="user/fake@email.com",
                Email="updated@email.com",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace=settings.QUICKSIGHT_NAMESPACE,
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
        user = UserFactory.create(username="fake@email.com")
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
                    "UserName": f"user/fake@email.com/{user.profile.sso_id}",
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
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                Role="AUTHOR",
                CustomPermissionsName="author-custom-permissions-test",
                UserName=f"user/fake@email.com/{user.profile.sso_id}",
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
                    "UserName": f"user/fake2@email.com/{user2.profile.sso_id}",
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
        username_suffix = (
            ""
            if settings.QUICKSIGHT_NAMESPACE == "default"
            else ("_" + settings.QUICKSIGHT_NAMESPACE)
        )

        # Assert
        assert mock_user_client.update_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                Role="ADMIN",
                UnapplyCustomPermissions=True,
                UserName=f"user/fake2@email.com/{user2.profile.sso_id}",
                Email="fake2@email.com",
            )
        ]
        assert mock_user_client.describe_user.call_args_list == [
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                UserName=f"quicksight_federation{username_suffix}/{user.profile.sso_id}",
            ),
            mock.call(
                AwsAccountId=mock.ANY,
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                UserName=f"quicksight_federation{username_suffix}/{user2.profile.sso_id}",
            ),
        ]
        assert len(mock_data_client.create_data_source.call_args_list) == 1
        assert len(mock_data_client.update_data_source.call_args_list) == 0


class TestSyncS3SSOUsers:
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_without_files_processes_nothing_and_doesnt_call_delete(self):
        with mock.patch(
            "dataworkspace.apps.applications.utils.get_s3_resource"
        ) as mock_get_s3_resource:
            _do_sync_s3_sso_users()
            mock_get_s3_resource().Bucket().delete_objects.assert_not_called()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_sync_with_empty_files_doesnt_run_db_query_but_deletes_file(self):
        with mock.patch(
            "dataworkspace.apps.applications.utils.get_s3_resource"
        ) as mock_get_s3_resource, mock.patch(
            "dataworkspace.apps.applications.utils._do_get_staff_sso_s3_object_summaries"
        ) as mock_get_s3_files, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed",
            return_value=[[], 1],
        ):
            mock_get_s3_files.return_value = [
                mock.MagicMock(
                    bucket_name="bucket_1",
                    key="a/today.jsonl.gz",
                    source_key="s3://bucket_1/a/today.jsonl.gz",
                    last_modified=datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%dZ"),
                )
            ]
            _do_sync_s3_sso_users()
            mock_get_s3_resource().Bucket().delete_objects.assert_has_calls(
                [
                    mock.call(
                        Delete={
                            "Objects": [
                                {"Key": "a/today.jsonl.gz"},
                            ]
                        }
                    )
                ]
            )

    @pytest.mark.django_db
    def test_sync_without_cache_uses_default_date(
        self,
    ):
        with mock.patch("dataworkspace.apps.applications.utils.get_s3_resource"), mock.patch(
            "dataworkspace.apps.applications.utils._do_get_staff_sso_s3_object_summaries"
        ) as mock_get_s3_files, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed",
            return_value=[[1], 1],
        ) as mock_get_seen_ids_and_last_processed:
            cache.delete("s3_sso_sync_last_published")
            mock_get_s3_files.return_value = [
                mock.MagicMock(
                    bucket_name="bucket_1",
                    key="a/today.jsonl.gz",
                    source_key="s3://bucket_1/a/today.jsonl.gz",
                    last_modified=datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%dZ"),
                )
            ]

            _do_sync_s3_sso_users()
            mock_get_seen_ids_and_last_processed.assert_has_calls(
                [
                    mock.call(
                        mock_get_s3_files.return_value,
                        mock.ANY,
                        datetime.datetime.fromtimestamp(
                            0, tz=datetime.datetime.now().astimezone().tzinfo
                        ),
                    )
                ]
            )

    @pytest.mark.django_db
    def test_sync_with_cache_uses_previous_date(
        self,
    ):
        with mock.patch("dataworkspace.apps.applications.utils.get_s3_resource"), mock.patch(
            "dataworkspace.apps.applications.utils._do_get_staff_sso_s3_object_summaries"
        ) as mock_get_s3_files, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed",
            return_value=[[1], 1],
        ) as mock_get_seen_ids_and_last_processed:
            cache.set("s3_sso_sync_last_published", datetime.datetime(2024, 7, 26, 12))
            mock_get_s3_files.return_value = [
                mock.MagicMock(
                    bucket_name="bucket_1",
                    key="a/today.jsonl.gz",
                    source_key="s3://bucket_1/a/today.jsonl.gz",
                    last_modified=datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%dZ"),
                )
            ]

            _do_sync_s3_sso_users()
            mock_get_seen_ids_and_last_processed.assert_has_calls(
                [
                    mock.call(
                        mock_get_s3_files.return_value,
                        mock.ANY,
                        datetime.datetime(2024, 7, 26, 12),
                    )
                ]
            )

    @pytest.mark.django_db
    def test_sync_with_active_user_not_in_file_set_to_inactive_for_full_sync(
        self,
    ):
        with mock.patch("dataworkspace.apps.applications.utils.get_s3_resource"), mock.patch(
            "dataworkspace.apps.applications.utils._do_get_staff_sso_s3_object_summaries"
        ) as mock_get_s3_files, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed"
        ) as mock_get_seen_ids_and_last_processed, mock.patch(
            "dataworkspace.apps.applications.utils._is_full_sync", return_value=True
        ):
            mock_get_s3_files.return_value = [mock.MagicMock(key="a/today.jsonl.gz")]

            inactive_user = UserFactory()
            inactive_user.profile.sso_status = "inactive"
            inactive_user.profile.save()

            active_user = UserFactory()
            active_user.profile.sso_status = "active"
            active_user.profile.save()

            active_user_not_in_file = UserFactory()
            active_user_not_in_file.profile.sso_status = "active"
            active_user_not_in_file.profile.save()

            mock_get_seen_ids_and_last_processed.return_value = (
                [
                    inactive_user.username,
                    active_user.username,
                ],
                datetime.datetime.now(),
            )

            _do_sync_s3_sso_users()

            User = get_user_model()
            assert (
                User.objects.filter(username=active_user.username).first().profile.sso_status
                == "active"
            )
            assert (
                User.objects.filter(username=active_user_not_in_file.username)
                .first()
                .profile.sso_status
                == "inactive"
            )
            assert (
                User.objects.filter(username=inactive_user.username).first().profile.sso_status
                == "inactive"
            )

    @pytest.mark.django_db
    def test_sync_with_active_user_not_in_file_not_changed_for_partial_sync(
        self,
    ):
        with mock.patch("dataworkspace.apps.applications.utils.get_s3_resource"), mock.patch(
            "dataworkspace.apps.applications.utils._do_get_staff_sso_s3_object_summaries"
        ) as mock_get_s3_files, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed"
        ) as mock_get_seen_ids_and_last_processed, mock.patch(
            "dataworkspace.apps.applications.utils._is_full_sync", return_value=False
        ):
            mock_get_s3_files.return_value = [mock.MagicMock(key="a/today.jsonl.gz")]

            active_user_not_in_file = UserFactory()
            active_user_not_in_file.profile.sso_status = "active"
            active_user_not_in_file.profile.save()

            mock_get_seen_ids_and_last_processed.return_value = (
                [],
                datetime.datetime.now(),
            )

            _do_sync_s3_sso_users()

            User = get_user_model()

            assert (
                User.objects.filter(username=active_user_not_in_file.username)
                .first()
                .profile.sso_status
                == "active"
            )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_do_get_staff_sso_s3_object_summaries_with_multiple_files_returns_in_correct_order(
        self,
    ):
        s3_object_1 = mock.MagicMock(
            bucket_name="bucket_1", key="a/today.jsonl.gz", last_modified=datetime.datetime.now()
        )
        s3_object_2 = mock.MagicMock(
            bucket_name="bucket_1",
            key="c/last_week.jsonl",
            last_modified=datetime.datetime.now() - datetime.timedelta(weeks=1),
        )
        s3_object_3 = mock.MagicMock(
            bucket_name="bucket_1",
            key="b/yesterday.jsonl",
            last_modified=datetime.datetime.now() - datetime.timedelta(days=1),
        )

        mock_bucket = mock.MagicMock()
        mock_bucket.objects.filter.return_value = [s3_object_1, s3_object_2, s3_object_3]

        summaries = _do_get_staff_sso_s3_object_summaries(mock_bucket)

        assert summaries == [s3_object_2, s3_object_3, s3_object_1]

    @pytest.mark.django_db
    def test_sync_overwrites_cache_with_newer_last_published_value(
        self,
    ):
        s3_object_1 = mock.MagicMock(
            bucket_name="bucket_1", key="a/today.jsonl.gz", last_modified=datetime.datetime.now()
        )
        with mock.patch(
            "dataworkspace.apps.applications.utils.get_s3_resource"
        ) as mock_get_s3_resource, mock.patch(
            "dataworkspace.apps.applications.utils._get_seen_ids_and_last_processed"
        ) as mock_get_seen_ids_and_last_processed:
            cache.set(
                "s3_sso_sync_last_published", datetime.datetime(2024, 7, 26, 12, tzinfo=tzlocal())
            )
            mock_get_s3_resource().Bucket().objects.filter.return_value = [
                s3_object_1,
            ]
            expected_cache_value = datetime.datetime.now(tz=tzlocal())
            mock_get_seen_ids_and_last_processed.return_value = [[1], expected_cache_value]
            _do_sync_s3_sso_users()
            assert cache.get("s3_sso_sync_last_published") == expected_cache_value

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_sync_s3_request_fails(self):
        with mock.patch(
            "dataworkspace.apps.applications.utils.get_s3_resource"
        ) as mock_get_s3_resource:
            with pytest.raises(Exception) as exc:
                mock_get_s3_resource.side_effect = Exception("No bucket")
                _do_sync_s3_sso_users()
            assert str(exc.value) == "No bucket"

        User = get_user_model()
        assert not User.objects.all()

    def test_get_seen_ids_and_last_processed_returns_unique_set_when_duplicate_ids_in_files(
        self,
    ):
        with mock.patch(
            "dataworkspace.apps.applications.utils._process_staff_sso_file"
        ) as mock_process_staff_sso_file:
            mock_process_staff_sso_file.side_effect = [
                ([1, 2, 3, 6, 7, 8], datetime.datetime.now()),
                ([1, 3, 5, 7, 10], datetime.datetime.now()),
            ]
            result = _get_seen_ids_and_last_processed(
                [
                    mock.MagicMock(
                        source_key="s3://bucket_1/a.jsonl.gz",
                    ),
                    mock.MagicMock(
                        source_key="s3://bucket_1/b.jsonl.gz",
                    ),
                ],
                mock.MagicMock(),
                datetime.datetime.now(),
            )

            assert len(result[0]) == 8
            assert result[0] == [1, 2, 3, 5, 6, 7, 8, 10]

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_file_without_cache_creates_all_users(self, sso_user_factory):
        user_1 = sso_user_factory()
        user_2 = sso_user_factory()
        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1), json.dumps(user_2)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime.fromtimestamp(0, tz=datetime.datetime.now().astimezone().tzinfo),
            )

            User = get_user_model()
            all_users = User.objects.all().order_by("date_joined")

            assert len(all_users) == 2
            assert str(all_users[0].profile.sso_id) == user_1["object"]["dit:StaffSSO:User:userId"]
            assert (
                str(all_users[0].profile.sso_status)
                == user_1["object"]["dit:StaffSSO:User:status"]
            )
            assert all_users[0].username == user_1["object"]["dit:StaffSSO:User:userId"]
            assert all_users[0].email == user_1["object"]["dit:emailAddress"][0]
            assert all_users[0].first_name == user_1["object"]["dit:firstName"]
            assert all_users[0].last_name == user_1["object"]["dit:lastName"]

            assert str(all_users[1].profile.sso_id) == user_2["object"]["dit:StaffSSO:User:userId"]
            assert (
                str(all_users[1].profile.sso_status)
                == user_2["object"]["dit:StaffSSO:User:status"]
            )
            assert all_users[1].username == user_2["object"]["dit:StaffSSO:User:userId"]
            assert all_users[1].email == user_2["object"]["dit:emailAddress"][0]
            assert all_users[1].first_name == user_2["object"]["dit:firstName"]
            assert all_users[1].last_name == user_2["object"]["dit:lastName"]

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_file_with_cache_ignores_users_before_last_published(
        self, sso_user_factory
    ):
        user_in_past = sso_user_factory(published_date=datetime.datetime(2023, 10, 1))
        user_to_be_included = sso_user_factory()
        m_open = mock.mock_open(
            read_data="\n".join([json.dumps(user_in_past), json.dumps(user_to_be_included)])
        )

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime(2024, 7, 26, 12, tzinfo=tzlocal()),
            )

            User = get_user_model()
            all_users = User.objects.all()

            assert len(all_users) == 1

            assert (
                str(all_users[0].profile.sso_id)
                == user_to_be_included["object"]["dit:StaffSSO:User:userId"]
            )
            assert (
                str(all_users[0].profile.sso_status)
                == user_to_be_included["object"]["dit:StaffSSO:User:status"]
            )
            assert (
                all_users[0].username == user_to_be_included["object"]["dit:StaffSSO:User:userId"]
            )
            assert all_users[0].email == user_to_be_included["object"]["dit:emailAddress"][0]
            assert all_users[0].first_name == user_to_be_included["object"]["dit:firstName"]
            assert all_users[0].last_name == user_to_be_included["object"]["dit:lastName"]

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_updates_existing_users_email(self, sso_user_factory):
        user_1 = sso_user_factory()

        user = UserFactory.create(email="should_be_changed@test.com")
        user.profile.sso_id = user_1["object"]["dit:StaffSSO:User:userId"]
        user.save()

        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime.fromtimestamp(0, tz=datetime.datetime.now().astimezone().tzinfo),
            )

            User = get_user_model()
            all_users = User.objects.all()

            assert len(all_users) == 1
            assert str(all_users[0].email) == user_1["object"]["dit:emailAddress"][0]

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_creates_role_if_user_can_access_tools(self, sso_user_factory):
        user_1 = sso_user_factory()

        can_access_tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        user = UserFactory.create(email=user_1["object"]["dit:emailAddress"][0])
        user.profile.sso_id = user_1["object"]["dit:StaffSSO:User:userId"]
        user.save()
        user.user_permissions.add(can_access_tools_permission)

        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ), mock.patch(
            "dataworkspace.apps.applications.utils.create_tools_access_iam_role_task"
        ) as create_tools_access_iam_role_task:
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime.fromtimestamp(0, tz=datetime.datetime.now().astimezone().tzinfo),
            )

            User = get_user_model()
            all_users = User.objects.all()

            assert len(all_users) == 1
            assert create_tools_access_iam_role_task.delay.call_args_list == [
                mock.call(
                    user.id,
                )
            ]

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_doesnt_create_role_if_user_cant_access_tools(
        self, sso_user_factory
    ):
        user_1 = sso_user_factory()

        user = UserFactory.create(email=user_1["object"]["dit:emailAddress"][0])
        user.profile.sso_id = user_1["object"]["dit:StaffSSO:User:userId"]
        user.save()

        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ), mock.patch(
            "dataworkspace.apps.applications.utils.create_tools_access_iam_role_task"
        ) as create_tools_access_iam_role_task:
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime.fromtimestamp(0, tz=datetime.datetime.now().astimezone().tzinfo),
            )

            User = get_user_model()
            all_users = User.objects.all()

            assert len(all_users) == 1
            assert not create_tools_access_iam_role_task.delay.called

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_doesnt_create_role_if_user_already_has_role(self, sso_user_factory):
        user_1 = sso_user_factory()

        can_access_tools_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        user = UserFactory.create(email=user_1["object"]["dit:emailAddress"][0])
        user.user_permissions.add(can_access_tools_permission)
        user.profile.sso_id = user_1["object"]["dit:StaffSSO:User:userId"]
        user.profile.tools_access_role_arn = "some-arn"
        user.save()

        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ), mock.patch(
            "dataworkspace.apps.applications.utils.create_tools_access_iam_role_task"
        ) as create_tools_access_iam_role_task:
            _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime.fromtimestamp(0, tz=datetime.datetime.now().astimezone().tzinfo),
            )

            User = get_user_model()
            all_users = User.objects.all()

            assert len(all_users) == 1
            assert not create_tools_access_iam_role_task.delay.called

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_with_empty_file_returns_empty_list_and_same_datetime(self):
        last_published = datetime.datetime.now(tz=tzlocal())
        m_open = mock.mock_open(read_data="\n")

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            process_staff_results = _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                last_published,
            )

            assert process_staff_results[0] == []
            assert process_staff_results[1] == last_published

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_returns_same_last_published_when_user_older_than_previous(
        self, sso_user_factory
    ):
        user_1 = sso_user_factory(published_date=datetime.datetime(2024, 1, 1, tzinfo=tzlocal()))
        last_published = datetime.datetime.now(tz=tzlocal())
        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            process_staff_results = _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                last_published,
            )

            assert process_staff_results[0] == [user_1["object"]["dit:StaffSSO:User:userId"]]
            assert process_staff_results[1] == last_published

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.django_db
    def test_process_staff_sso_returns_latest_user_last_published_when_newer_than_previous(
        self, sso_user_factory
    ):
        user_1 = sso_user_factory(published_date=datetime.datetime.now(tz=tzlocal()))

        m_open = mock.mock_open(read_data="\n".join([json.dumps(user_1)]))

        with mock.patch(
            "dataworkspace.apps.applications.utils.smart_open",
            m_open,
            create=True,
        ):
            process_staff_results = _process_staff_sso_file(
                mock.MagicMock(),
                "file.jsonl.gz",
                datetime.datetime(2024, 7, 26, 12, tzinfo=tzlocal()),
            )

            assert process_staff_results[0] == [get_user_model().objects.all().first().username]
            assert process_staff_results[1] == parser.parse(user_1["published"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.parametrize(
        ("filenames"),
        (
            (["full"]),
            (["full_", "full"]),
        ),
    )
    def test_is_full_sync_returns_true_when_all_files_contain_full(self, filenames):
        files = [
            mock.MagicMock(
                key=filename,
            )
            for filename in filenames
        ]
        assert _is_full_sync(files)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    @pytest.mark.parametrize(
        ("filenames"),
        (
            (["anything"]),
            (["anything", "full"]),
        ),
    )
    def test_is_full_sync_returns_false_when_all_files_do_not_contain_full(self, filenames):
        files = [
            mock.MagicMock(
                key=filename,
            )
            for filename in filenames
        ]
        assert _is_full_sync(files) is False


class TestCreateToolsAccessIAMRoleTask:
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.applications.utils.create_tools_access_iam_role")
    def test_task_creates_iam_role(self, mock_create_tools_access_iam_role):
        user = UserFactory.create(username="00000000-0000-0000-0000-000000000001")
        user.profile.sso_id = "00000000-0000-0000-0000-000000000001"
        user.profile.home_directory_efs_access_point_id = "some-access-point-id"
        user.save()

        _do_create_tools_access_iam_role(user.id)

        assert mock_create_tools_access_iam_role.call_args_list == [
            mock.call(
                user.id,
                user.email,
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
        assert tables.count() == table_count + 2  # 1 table for select, 1 for insert
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
        assert tables.count() == table_count + 2  # 1 table for select, 1 for insert
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


class TestRemoveToolsAccessForUsersWithExpiredCert:
    permissions_codenames = (
        "start_all_applications",
        "develop_visualisations",
        "access_quicksight",
        "access_appstream",
    )

    total_days = 366 if calendar.isleap(datetime.date.today().year) else 365
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=total_days)
    one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)

    def setup_user_tools_cert(self, user, cert_date, codenames=()):
        for codename in codenames:
            tools_permission = Permission.objects.get(
                codename=codename,
                content_type=ContentType.objects.get_for_model(ApplicationInstance),
            )
            user.user_permissions.add(tools_permission)

        user.profile.tools_certification_date = cert_date
        user.save()

    @pytest.mark.django_db
    def test_removes_permissions_when_cert_has_expired(self):
        user = UserFactory.create()
        self.setup_user_tools_cert(user, self.one_year_ago.date(), self.permissions_codenames)

        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is True
        remove_tools_access_for_users_with_expired_cert()
        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is False

    @pytest.mark.django_db
    def test_does_not_remove_permissions_when_cert_is_valid(self):
        user = UserFactory.create()
        self.setup_user_tools_cert(user, self.one_day_ago.date(), self.permissions_codenames)

        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is True
        remove_tools_access_for_users_with_expired_cert()
        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is True

    @pytest.mark.django_db
    def test_does_not_effect_permissions_when_user_has_no_permissions_but_has_valid_cert(self):
        user = UserFactory.create()
        self.setup_user_tools_cert(user, self.one_day_ago.date())

        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is False
        remove_tools_access_for_users_with_expired_cert()
        can_start_tools = user.user_permissions.filter(
            codename__in=self.permissions_codenames
        ).exists()
        assert can_start_tools is False


class TestSelfCertifyRenewalEmailNotification:
    total_days = 366 if calendar.isleap(datetime.date.today().year) else 365
    year_ago_cert_date = datetime.datetime.now() - datetime.timedelta(days=total_days)
    one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)

    def setup_cert(self, user, cert_date):
        user.profile.tools_certification_date = cert_date
        user.profile.is_renewal_email_sent = False
        user.save()

    @pytest.mark.django_db
    @override_settings(NOTIFY_SELF_CERTIFY_RENEWAL_TEMPLATE_ID="000000000000000000000000010")
    @patch("dataworkspace.apps.applications.utils.send_email")
    def test_email_is_sent(self, mock_send_email, user):
        self.setup_cert(user, self.year_ago_cert_date)

        self_certify_renewal_email_notification()
        user_profile = (
            Profile.objects.filter(sso_id=user.profile.sso_id).select_related("user").first()
        )

        assert mock_send_email.call_args_list == [
            call(
                template_id="000000000000000000000000010",
                email_address=user.email,
            )
        ]
        assert user_profile.is_renewal_email_sent is True

    @pytest.mark.django_db
    @override_settings(NOTIFY_SELF_CERTIFY_RENEWAL_TEMPLATE_ID="000000000000000000000000010")
    @patch("dataworkspace.apps.applications.utils.send_email")
    def test_email_is_not_sent(self, mock_send_email, user):
        self.setup_cert(user, self.one_day_ago)

        self_certify_renewal_email_notification()
        user_profile = (
            Profile.objects.filter(sso_id=user.profile.sso_id).select_related("user").first()
        )

        mock_send_email.assert_not_called()
        assert user_profile.is_renewal_email_sent is False

    @pytest.mark.django_db
    @override_settings(NOTIFY_SELF_CERTIFY_RENEWAL_TEMPLATE_ID="000000000000000000000000010")
    @patch("dataworkspace.apps.applications.utils.send_email")
    def test_email_is_not_sent_when_the_service_fails(self, mock_send_email, user):
        self.setup_cert(user, self.year_ago_cert_date)

        mock_send_email.side_effect = Exception("Email is not sent")

        with pytest.raises(Exception) as e:
            self_certify_renewal_email_notification()

            assert e.value is mock_send_email.side_effect

    @pytest.mark.django_db
    @override_settings(NOTIFY_SELF_CERTIFY_RENEWAL_TEMPLATE_ID="000000000000000000000000010")
    @patch("dataworkspace.apps.applications.utils.send_email")
    def test_renewel_email_is_not_sent_when_cert_date_is_missing(self, mock_send_email, user):
        self.setup_cert(user, None)
        self_certify_renewal_email_notification()
        user_profile = (
            Profile.objects.filter(sso_id=user.profile.sso_id).select_related("user").first()
        )
        mock_send_email.assert_not_called()
        assert user_profile.is_renewal_email_sent is False
