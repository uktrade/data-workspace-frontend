from datetime import datetime

import factory
import mock
import pytest
import uuid

from dataworkspace.apps.core.utils import get_s3_prefix
from dataworkspace.apps.your_files.tasks import (
    collect_your_files_stats,
    collect_your_files_stats_for_user,
    _sync_user_storage,
)
from dataworkspace.tests import factories

from waffle.testutils import override_switch


@pytest.mark.django_db
class TestCollectYourFilesStatsCeleryTask:
    @mock.patch("dataworkspace.apps.your_files.tasks.collect_your_files_stats_for_user")
    @override_switch("enable_your_files_stats_collection", active=False)
    def test_collect_your_files_stats_when_waffle_flag_inactive(self, mock_user_stats):
        user = factories.UserFactory.create()
        user.profile.sso_status = "active"
        user.profile.first_login = datetime.now()
        user.profile.save()

        collect_your_files_stats()
        assert not mock_user_stats.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active(self, mock_sync_user_storage):
        user = factories.UserFactory.create()
        user.profile.sso_status = "active"
        user.profile.first_login = datetime.now()
        user.profile.save()

        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(user, mock.ANY)

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active_ignores_inactive_users(
        self, mock_sync_user_storage
    ):
        active_user = factories.UserFactory.create()
        active_user.profile.sso_status = "active"
        active_user.profile.first_login = datetime.now()
        active_user.profile.save()

        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "inactive"
        inactive_user.profile.first_login = datetime.now()
        inactive_user.profile.save()

        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active_ignores_never_logged_in_users(
        self, mock_sync_user_storage
    ):
        active_user = factories.UserFactory.create()
        active_user.profile.sso_status = "active"
        active_user.profile.first_login = datetime.now()
        active_user.profile.save()

        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "active"
        inactive_user.profile.first_login = None
        inactive_user.profile.save()

        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)


@pytest.mark.django_db
class TestSyncUserStorage:
    def test_collect_your_files_stats_for_single_user(self):
        user = factories.UserFactory.create()
        user.profile.sso_status = "active"
        user.profile.first_login = datetime.now()
        user.profile.save()

        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": f"{get_s3_prefix(str(user.profile.sso_id))}bigdata/test",
                        "Size": 20,
                    },
                    {
                        "Key": f"{get_s3_prefix(str(user.profile.sso_id))}/test",
                        "Size": 10,
                    },
                ]
            },
        ]

        _sync_user_storage(user, paginator)
        assert user.your_files_stats.count() == 1
        assert user.your_files_stats.latest().total_size_bytes == 10
        # users = factories.UserFactory.create_batch(5, id=factory.Iterator([i for i in range(5)]))

        # for user in users:
        #     user.profile.sso_status = "active"
        #     user.profile.first_login = datetime.now()
        #     user.profile.save()

        #     mock_client.return_value.get_paginator.return_value.paginate.return_value = [
        #         {
        #             "Contents": [
        #                 {
        #                     "Key": f"{get_s3_prefix(str(1))}bigdata/test",
        #                     "Size": 10,
        #                 },
        #                 {
        #                     "Key": f"{get_s3_prefix(str(1))}/test",
        #                     "Size": 10,
        #                 },
        #             ]
        #         },
        #     ]

        #     collect_your_files_stats()
        # assert user.your_files_stats.count() == 1
        # assert user.your_files_stats.latest().total_size_bytes == 10
