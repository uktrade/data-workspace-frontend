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
from dataworkspace.apps.your_files.models import YourFilesUserPrefixStats
from dataworkspace.tests import factories

from waffle.testutils import override_switch


@pytest.fixture
def active_user():
    user = factories.UserFactory.create()
    user.profile.sso_status = "active"
    user.profile.first_login = datetime.now()
    user.profile.save()
    return user


@pytest.mark.django_db
class TestCollectYourFilesStatsCeleryTask:
    @mock.patch("dataworkspace.apps.your_files.tasks.collect_your_files_stats_for_user")
    @override_switch("enable_your_files_stats_collection", active=False)
    def test_collect_your_files_stats_when_waffle_flag_inactive(self, mock_user_stats):
        collect_your_files_stats()
        assert not mock_user_stats.called

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active(
        self, mock_sync_user_storage, active_user
    ):
        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active_ignores_inactive_users(
        self, mock_sync_user_storage, active_user
    ):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "inactive"
        inactive_user.profile.first_login = datetime.now()
        inactive_user.profile.save()

        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)

    @mock.patch("dataworkspace.apps.your_files.tasks._sync_user_storage")
    @override_switch("enable_your_files_stats_collection", active=True)
    def test_collect_your_files_stats_when_waffle_flag_active_ignores_never_logged_in_users(
        self, mock_sync_user_storage, active_user
    ):
        inactive_user = factories.UserFactory.create()
        inactive_user.profile.sso_status = "active"
        inactive_user.profile.first_login = None
        inactive_user.profile.save()

        collect_your_files_stats()
        mock_sync_user_storage.assert_called_once_with(active_user, mock.ANY)


@pytest.mark.django_db
class TestSyncUserStorage:
    def test_collect_your_files_stats_for_user_without_files_creates_empty_stats_entry(
        self, active_user
    ):
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {"Contents": []},
        ]

        _sync_user_storage(active_user, paginator)
        assert active_user.your_files_stats.count() == 1
        assert active_user.your_files_stats.latest().total_size_bytes == 0

    def test_collect_your_files_stats_for_user_with_only_bigdata_creates_empty_stats_entry(
        self, active_user
    ):
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

    def test_collect_your_files_stats_for_user_with_new_files_creates_new_stats_entry(
        self, active_user
    ):
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

    def test_collect_your_files_stats_for_user_with_no_file_changes_updates_previous_stats_entry(
        self, active_user
    ):
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
