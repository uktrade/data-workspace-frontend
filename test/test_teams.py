import asyncio
import logging
import os
import textwrap
import unittest

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
)

logger = logging.getLogger(__name__)
SSO_USER_ID = "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2"


async def create_visualisation_ddl(name):
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
            gitlab_project_id=3,
            visible=True
        )
        VisualisationCatalogueItem.objects.create(
            name="Test {name}",
            user_access_type="REQUIRES_AUTHORIZATION",
            slug="{name}",
            visualisation_template=template
        )
        """
    ).encode('ascii')
    give_perm = await asyncio.create_subprocess_shell(
        'django-admin shell',
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
        visualisation_name = "testvisualisation"

        # BEGIN TEST BOILERPLATE ....
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

        dataset_id_test_dataset = '70ce6fdd-1791-4806-bbe0-4cf880a9cc37'
        table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'

        stdout, stderr, code = await create_private_dataset(
            'my_database',
            'MASTER',
            dataset_id_test_dataset,
            'test_dataset',
            table_id,
            'test_dataset',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertNotIn("Test Application", content)

        stdout, stderr, code = await create_visualisation_ddl(visualisation_name)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms(visualisation_name)
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://testvisualisation.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn(f"{visualisation_name} is loading...", application_content_1)

        await until_non_202(
            session, f"http://{visualisation_name}.dataworkspace.test:8000/"
        )

        # END BOILERPLATE
        # Actual teams specific tests here ...

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "GET",
            f"http://{visualisation_name}.dataworkspace.test:8000/get",
            headers=sent_headers,
        ) as response:

            received_content = await response.json()
            received_status_code = response.status

        print(received_content)
        print(received_status_code)

        # self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_status_code, 200)
