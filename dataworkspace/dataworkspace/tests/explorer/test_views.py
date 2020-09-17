from django.urls import reverse
from waffle.testutils import override_flag

from dataworkspace.tests.common import BaseTestCase
from dataworkspace.utils import DATA_EXPLORER_FLAG


class TestExplorerIndex(BaseTestCase):
    def test_protected_by_waffle_flag(self):
        response = self._authenticated_get(reverse('explorer:index'))
        assert response.status_code == 403

        with override_flag(DATA_EXPLORER_FLAG, active=True):
            response = self._authenticated_get(reverse('explorer:index'))
            assert response.status_code == 200
