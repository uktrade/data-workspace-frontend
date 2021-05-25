import asyncio
import logging
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
    create_visualisation_dataset,
    create_private_dataset,
)

logger = logging.getLogger(__name__)
SSO_USER_ID = "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2"


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

        async with session.request(
            "GET", "http://dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertNotIn("Test Application", content)

        stdout, stderr, code = await create_visualisation_dataset(visualisation_name, 3)
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
            f"http://{visualisation_name}.dataworkspace.test:8000/test_external_db/table_name",
            headers=sent_headers,
        ) as response:
            # received_content = await response.json()
            received_status_code = response.status

        # self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_status_code, 200)
