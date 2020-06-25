import mock
import pytest
import redis
from django.core.cache import cache

from dataworkspace.apps.applications.utils import delete_unused_datasets_users


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
