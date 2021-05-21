import asyncio
import logging
import unittest

from test.sso import create_sso_with_auth
from test.test_application import until_succeeds, create_application, client_session

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
        logger.debug("test_launch_tool_sets_teams_schema")

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        sso_cleanup, _ = await create_sso_with_auth(True, SSO_USER_ID)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        logger.debug(content)
        self.assertNotIn('Test Application', content)
