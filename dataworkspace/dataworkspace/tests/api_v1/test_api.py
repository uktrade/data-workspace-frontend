import uuid

import boto3
import mock
import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from dataworkspace.apps.core.errors import ToolInvalidUserError
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase
from dataworkspace.tests.core.factories import TeamFactory, TeamMembershipFactory
from dataworkspace.tests.factories import UserFactory


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


@pytest.mark.django_db
def test_adding_user_to_team_after_email_change_gives_permission_to_team_folder(settings):
    iam_client = boto3.client("iam", endpoint_url=settings.IAM_LOCAL_ENDPOINT_URL)

    # IAM role changes run asynchronously, and this forces them to run synchronously so we can
    # more robustly assert on changes to them
    settings.CELERY_TASK_ALWAYS_EAGER = True

    # Create user with deliberately not hard coded email so the factory creates a random one, so we
    # are less likely to be effected by other tests that could have setup policies in LocalStack
    user = UserFactory()
    client = Client(
        **{
            "HTTP_SSO_PROFILE_EMAIL": user.email,
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": user.email,
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_SSO_PROFILE_LAST_NAME": "Exampleson",
            "HTTP_SSO_PROFILE_FIRST_NAME": "Frank",
        }
    )
    client.force_login(user)

    # Create teams
    team_a = TeamFactory()
    team_a_prefix = f"teams/{team_a.schema_name}"
    team_b = TeamFactory()
    team_b_prefix = f"teams/{team_b.schema_name}"

    # Ideally would would make a request using the credentials and get 200/403 on the team folder
    # However, this is a LockStack pro feature. A reasonable next best thing is to check that
    # the policy does not contain the team folder name until we are added to the team. This is
    # unfortunately brittle to how policies are applied ot the role (e.g. if they're inline
    # or stand alone policies that are then attached)
    def get_policy_statements():
        # Get credentials for the user (just like in Your Files)
        credentials_response = client.get(reverse("api_v1:aws-credentials"))
        assert credentials_response.status_code == 200
        credentials_response_json = credentials_response.json()

        role_name = (
            boto3.client(
                "sts",
                endpoint_url=settings.S3_LOCAL_ENDPOINT_URL,
                aws_access_key_id=credentials_response_json["AccessKeyId"],
                aws_secret_access_key=credentials_response_json["SecretAccessKey"],
                aws_session_token=credentials_response_json["SessionToken"],
            )
            .get_caller_identity()["Arn"]
            .split("/")[1]
        )
        policy_names = iam_client.list_role_policies(
            RoleName=role_name,
        )["PolicyNames"]

        return "".join(
            [
                str(
                    iam_client.get_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name,
                    )["PolicyDocument"]
                )
                for policy_name in policy_names
            ]
        )

    # Assert the user cannot access either team folder (roughly)
    assert team_a_prefix not in get_policy_statements()
    assert team_b_prefix not in get_policy_statements()

    # Getting credentials for the first time, as in aws-credentials caches the iam role arn on
    # the user, and so for a realistic test using the user further we should refresh it
    user.refresh_from_db()

    # Add the user to the team_a
    TeamMembershipFactory(team=team_a, user=user)

    # Assert the user can access the team_a folder and not team_b (roughly)
    assert team_a_prefix in get_policy_statements()
    assert team_b_prefix not in get_policy_statements()

    # Change the user's email address
    user.email = str(uuid.uuid4()) + "@test.com"
    user.save(update_fields=["email"])
    client = Client(
        **{
            "HTTP_SSO_PROFILE_EMAIL": user.email,
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": user.email,
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
            "HTTP_SSO_PROFILE_USER_ID": user.username,
            "HTTP_SSO_PROFILE_LAST_NAME": "Exampleson",
            "HTTP_SSO_PROFILE_FIRST_NAME": "Frank",
        }
    )
    client.force_login(user)

    # Add the user to the team_b
    TeamMembershipFactory(team=team_b, user=user)

    # Assert the user can now access both team folders (roughly)
    assert team_a_prefix in get_policy_statements()
    assert team_b_prefix in get_policy_statements()
