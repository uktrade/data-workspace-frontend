import mock
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from dataworkspace.apps.core.errors import ToolInvalidUserError
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
                args=("testapplication-{}".format(str(self.user.profile.sso_id)[:8]),),
            )
        )
        self.assertEqual(response.status_code, 200)
        mock_spawn.assert_called_once()

    @mock.patch("dataworkspace.apps.api_v1.views.application_api_is_allowed")
    def test_generic_403(self, mock_api_allowed):
        mock_api_allowed.side_effect = PermissionDenied()
        response = self._authenticated_get(
            reverse(
                "api_v1:application-detail",
                args=("testapplication-123456789",),
            )
        )
        # pylint: disable=maybe-no-member
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"redirect_url": "/error_403"})

    @mock.patch("dataworkspace.apps.api_v1.views.application_api_is_allowed")
    def test_custom_403(self, mock_api_allowed):
        mock_api_allowed.side_effect = ToolInvalidUserError()
        response = self._authenticated_get(
            reverse(
                "api_v1:application-detail",
                args=("testapplication-123456789",),
            )
        )
        # pylint: disable=maybe-no-member
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"redirect_url": "/error_403_tool_invalid"})
