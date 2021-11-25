import mock
from django.urls import reverse

from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase


class TestApplicationAPI(BaseTestCase):
    databases = ["default", "my_database"]

    @mock.patch("dataworkspace.apps.api_v1.views.application_api_is_allowed")
    @mock.patch("dataworkspace.apps.api_v1.views.spawn")
    def test_start_application_with_invalid_table(self, mock_api_allowed, mock_spawn):
        # Test that any SourceTable objects that don't exist in the db do
        # not break the loading of applications
        factories.ApplicationTemplateFactory.create(host_basename="testapplication")
        factories.SourceTableFactory.create(
            database=factories.DatabaseFactory.create(memorable_name="my_database"),
            dataset=factories.DataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
            ),
            table="doesnotexist",
        )
        mock_api_allowed.return_value = True
        response = self._authenticated_put(
            reverse(
                "api_v1:application-detail",
                args=(f"testapplication-{str(self.user.profile.sso_id)[:8]}",),
            )
        )
        self.assertEqual(response.status_code, 200)
        mock_spawn.assert_called_once()
