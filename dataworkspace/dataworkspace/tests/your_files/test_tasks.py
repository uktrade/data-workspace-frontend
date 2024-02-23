from datetime import datetime

import mock
import pytest


from waffle.testutils import override_switch

from dataworkspace.apps.core.utils import get_s3_prefix
from dataworkspace.apps.your_files.tasks import (
    collect_your_files_stats_all_users,
    collect_your_files_stats_single_user,
    _sync_user_storage,
)
from dataworkspace.apps.your_files.models import YourFilesUserPrefixStats
from dataworkspace.tests import factories


@pytest.fixture
def active_user():
    user = factories.UserFactory.create()
    user.profile.sso_status = "active"
    user.profile.first_login = datetime.now()
    user.profile.save()
    return user


@pytest.mark.django_db
class TestCollectYourFilesStatsAllUsersCeleryTask:
    @mock.patch("dataworkspace.apps.your_files.tasks._get_s3_list_objects_paginator")
    @override_switch("enable_your_files_stats_collection", active=False)
    def test_all_users_your_file_stats_when_waffle_flag_inactive(self, mock_paginator):
        collect_your_files_stats_all_users()
        assert not mock_paginator.called

    @mock.patch("dataworkspace.apps.your_files.tasks._get_s3_list_objects_paginator")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_all_users_your_file_stats_when_waffle_flag_active(self, mock_paginator, active_user):
        collect_your_files_stats_all_users()
        assert mock_paginator.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_all_users_your_file_stats_when_waffle_flag_active_ignores_inactive_users(
        self, mock_sync_user_storage, active_user
    ):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "inactive"
        inactive_user.profile.first_login = datetime.now()
        inactive_user.profile.save()

        collect_your_files_stats_all_users()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_all_users_your_file_stats_when_waffle_flag_active_ignores_never_logged_in_users(
        self, mock_sync_user_storage, active_user
    ):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "active"
        inactive_user.profile.first_login = None
        inactive_user.profile.save()

        collect_your_files_stats_all_users()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)


@pytest.mark.django_db
class TestCollectYourFilesStatsSingleUserCeleryTask:
    @mock.patch("dataworkspace.apps.your_files.tasks._get_s3_list_objects_paginator")
    @override_switch("enable_your_files_stats_collection", active=False)
    def test_single_user_your_file_stats_when_waffle_flag_inactive(self, mock_paginator):
        collect_your_files_stats_single_user(1)
        assert not mock_paginator.called

    @mock.patch("dataworkspace.apps.your_files.tasks._get_s3_list_objects_paginator")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_single_user_your_file_stats_when_waffle_flag_active(self, mock_paginator):
        collect_your_files_stats_single_user(1)
        assert mock_paginator.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_single_user_your_file_stats_with_invalid_user_id(self, mock_sync_user_storage):
        collect_your_files_stats_single_user(1)
        assert not mock_sync_user_storage.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_single_user_your_file_stats_with_inactive_user(self, mock_sync_user_storage):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "inactive"
        inactive_user.profile.first_login = datetime.now()
        inactive_user.profile.save()

        collect_your_files_stats_single_user(inactive_user.id)
        assert not mock_sync_user_storage.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_single_user_your_file_stats_with_never_logged_in_user(self, mock_sync_user_storage):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "active"
        inactive_user.profile.first_login = None
        inactive_user.profile.save()

        collect_your_files_stats_single_user(inactive_user.id)
        assert not mock_sync_user_storage.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_single_user_your_file_stats_with_active_user(
        self, mock_sync_user_storage, active_user
    ):
        collect_your_files_stats_single_user(active_user.id)
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)


@pytest.mark.django_db
class TestSyncUserStorage:
    def test_user_without_files_creates_empty_stats_entry(self, active_user):
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {"Contents": []},
        ]

        _sync_user_storage(active_user, paginator)
        assert active_user.your_files_stats.count() == 1
        assert active_user.your_files_stats.latest().total_size_bytes == 0

    def test_user_with_only_bigdata_creates_empty_stats_entry(self, active_user):
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": f"{get_s3_prefix(str(active_user.profile.sso_id))}bigdata/test",
                        "Size": 20,
                    },
                ]
            },
        ]

        _sync_user_storage(active_user, paginator)
        assert active_user.your_files_stats.count() == 1
        assert active_user.your_files_stats.latest().total_size_bytes == 0

    def test_user_with_new_files_creates_new_stats_entry(self, active_user):
        YourFilesUserPrefixStats.objects.create(
            user=active_user,
            prefix="/abc",
            total_size_bytes=100,
            num_files=5,
            num_large_files=0,
        )
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": f"{get_s3_prefix(str(active_user.profile.sso_id))}/test",
                        "Size": 55,
                    },
                ]
            },
        ]

        _sync_user_storage(active_user, paginator)
        assert active_user.your_files_stats.count() == 2
        assert active_user.your_files_stats.latest().total_size_bytes == 55

    def test_user_with_no_file_changes_updates_previous_stats_entry(self, active_user):
        YourFilesUserPrefixStats.objects.create(
            user=active_user,
            prefix="/abc",
            total_size_bytes=55,
            num_files=1,
            num_large_files=0,
        )
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": f"{get_s3_prefix(str(active_user.profile.sso_id))}/test",
                        "Size": 55,
                    },
                ]
            },
        ]

        _sync_user_storage(active_user, paginator)
        assert active_user.your_files_stats.count() == 1
        assert active_user.your_files_stats.latest().total_size_bytes == 55
