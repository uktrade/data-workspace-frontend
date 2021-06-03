import asyncio
import logging
import os
import textwrap
import unittest

from faker import Faker

from dataworkspace.apps.core.utils import get_team_schema_name
from test.sso import create_sso_with_auth
from test.test_application import (
    until_succeeds,
    create_application,
    client_session,
    flush_database,
    flush_redis,
    until_non_202,
    give_user_visualisation_perms,
    create_private_dataset,
    give_user_dataset_perms,
    toggle_visualisation_visibility,
    give_visualisation_dataset_perms,
)

fake = Faker()

logger = logging.getLogger(__name__)
SSO_USER_ID = "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2"


async def add_user_to_team(user_sso_id: str, team_name: str):
    python_code = textwrap.dedent(
        f"""\

        from django.contrib.auth import get_user_model
        from dataworkspace.apps.core.models import Team, TeamMembership

        User = get_user_model()

        user = User.objects.get(profile__sso_id="{user_sso_id}")

        team, _ = Team.objects.get_or_create(name="{team_name}")
        membership, _ = TeamMembership.objects.get_or_create(user_id=user, team_id=team)

        """
    ).encode("ascii")

    add_to_team = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await add_to_team.communicate(python_code)
    code = await add_to_team.wait()

    return stdout, stderr, code


async def create_visualisation_ddl(name, gitlab_project_id=3):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import (
            VisualisationTemplate,
        )
        from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
        template = VisualisationTemplate.objects.create(
            host_basename="{name}",
            nice_name="Test {name}",
            spawner="PROCESS",
            spawner_options='{{"CMD":["python3", "/test/ddl_server.py"]}}',
            spawner_time=60,
            gitlab_project_id={gitlab_project_id},
            visible=True
        )
        VisualisationCatalogueItem.objects.create(
            name="Test {name}",
            user_access_type="REQUIRES_AUTHORIZATION",
            slug="{name}",
            visualisation_template=template
        )
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


def async_test(func):
    def wrapper(*args, **kwargs):
        future = func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)

    return wrapper


class TestTeams(unittest.TestCase):
    def add_async_cleanup(self, coroutine):
        loop = asyncio.get_event_loop()
        self.addCleanup(loop.run_until_complete, coroutine())

    @async_test
    async def test_launch_tool_sets_teams_schema(self):
        visualisation_name = "testvisualisation-a"
        test_team_name = fake.company()

        expected_team_name = get_team_schema_name(test_team_name)

        await flush_database()
        await flush_redis()
        logger.debug("test_launch_tool_sets_teams_schema")

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        sso_cleanup, _ = await create_sso_with_auth(True, SSO_USER_ID)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure user created
        async with session.request(
            "GET", "http://dataworkspace.test:8000/"
        ) as response:
            await response.text()

        dataset_id_test_dataset = "70ce6fdd-1791-4806-bbe0-4cf880a9cc37"
        table_id = "5a2ee5dd-f025-4939-b0a1-bb85ab7504d7"

        stdout, stderr, code = await create_private_dataset(
            "test_external_db",
            "MASTER",
            dataset_id_test_dataset,
            "test_dataset",
            table_id,
            "test_dataset",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        dataset_id_dataset_2 = "ccddcf9a-4997-4761-bd5a-06854d0a6483"
        table_id = "426f6862-9880-4a1f-82a1-8496a5400820"
        stdout, stderr, code = await create_private_dataset(
            "test_external_db2",
            "MASTER",
            dataset_id_dataset_2,
            "dataset_2",
            table_id,
            "dataset_2",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await create_visualisation_ddl(visualisation_name, 3)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_dataset_perms("test_dataset")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        stdout, stderr, code = await toggle_visualisation_visibility(
            visualisation_name, True
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms(visualisation_name)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_visualisation_dataset_perms(
            visualisation_name, "test_dataset"
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await add_user_to_team(SSO_USER_ID, test_team_name)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"", stderr)
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertNotIn("Test Application", content)

        async with session.request(
            "GET", f"http://{visualisation_name}.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn(f"{visualisation_name} is loading...", application_content_1)

        await until_non_202(
            session, f"http://{visualisation_name}.dataworkspace.test:8000/"
        )

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "GET",
            f"http://{visualisation_name}.dataworkspace.test:8000/query_schema/test_external_db",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_status_code = response.status

        self.assertEqual(received_status_code, 200)
        self.assertIn(expected_team_name, received_content["rows"])
