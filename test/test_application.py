import asyncio

import json
import re
import unittest
import uuid

from test.utility_functions import (
    async_test,
    add_user_to_team,
    client_session,
    create_application,
    create_server,
    create_private_dataset,
    create_sso,
    create_visualisation_dataset,
    create_visualisation_echo,
    ensure_team_created,
    flush_database,
    flush_redis,
    give_user_app_perms,
    give_user_dataset_perms,
    give_visualisation_dataset_perms,
    give_user_visualisation_developer_perms,
    give_user_visualisation_perms,
    make_all_tools_visible,
    set_visualisation_wrap,
    toggle_visualisation_visibility,
    until_non_202,
    until_succeeds,
)

from aiohttp import web


class TestApplication(unittest.TestCase):
    """Tests the behaviour of the application, including Proxy"""

    def add_async_cleanup(self, coroutine):
        loop = asyncio.get_event_loop()
        self.addCleanup(loop.run_until_complete, coroutine())

    @async_test
    async def test_application_shows_content_if_authorized(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        _, _, _ = await make_all_tools_visible()

        # Ensure the user doesn't see the application link since they don't
        # have permission
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            content = await response.text()
        self.assertNotIn("Test Application", content)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # Make a request to the tools page
        async with session.request("GET", "http://dataworkspace.test:8000/tools/") as response:
            content = await response.text()

        # Ensure the user sees the link to the application
        self.assertEqual(200, response.status)
        self.assertIn("Test Application</button>", content)

        self.assertIn('action="http://testapplication-23b40dd9.dataworkspace.test:8000/"', content)

        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("Test Application is loading...", application_content_1)

        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_2 = await response.text()

        self.assertIn("Test Application is loading...", application_content_2)

        await until_non_202(session, "http://testapplication-23b40dd9.dataworkspace.test:8000/")

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {"from-downstream": "downstream-header-value"}

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        # We are authorized by SSO, and can do non-GETs
        async def sent_content():
            for _ in range(10000):
                yield b"Some content"

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "PATCH",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            data=sent_content(),
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "PATCH")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_content["content"], "Some content" * 10000)
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        # Assert that transfer-encoding does not become chunked unnecessarily
        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/http"
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content["headers"].keys()]
        self.assertNotIn("transfer-encoding", header_keys)

        async with session.request(
            "PATCH",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            data=b"1234",
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content["headers"].keys()]
        self.assertNotIn("transfer-encoding", header_keys)
        self.assertEqual(received_content["content"], "1234")

        # Make a websockets connection to the proxy
        sent_headers = {"from-downstream-websockets": "websockets-header-value"}
        async with session.ws_connect(
            "http://testapplication-23b40dd9.dataworkspace.test:8000/websockets",
            headers=sent_headers,
        ) as wsock:
            msg = await wsock.receive()
            headers = json.loads(msg.data)

            await wsock.send_bytes(b"some-\0binary-data")
            msg = await wsock.receive()
            received_binary_content = msg.data

            await wsock.send_str("some-text-data")
            msg = await wsock.receive()
            received_text_content = msg.data

            await wsock.close()

        self.assertEqual(headers["from-downstream-websockets"], "websockets-header-value")
        self.assertEqual(received_binary_content, b"some-\0binary-data")
        self.assertEqual(received_text_content, "some-text-data")

        # Test that if we will the application, and restart, we initially
        # see an error that the application stopped, but then after refresh
        # we load up the application succesfully
        await cleanup_application_1()
        cleanup_application_2 = await create_application()
        self.add_async_cleanup(cleanup_application_2)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            error_content = await response.text()

        self.assertIn("Application STOPPED", error_content)

        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertIn("Test Application is loading...", content)

        await until_non_202(session, "http://testapplication-23b40dd9.dataworkspace.test:8000/")

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

    @async_test
    async def test_db_application_can_read_and_write_to_private_and_team_schemas(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure the record has been created
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        # Slightly unfortunately, we need a dataset in the database for the
        # user to have their private schema created
        dataset_id_test_dataset = "70ce6fdd-1791-4806-bbe0-4cf880a9cc37"
        table_id = "5a2ee5dd-f025-4939-b0a1-bb85ab7504d7"
        stdout, stderr, code = await create_private_dataset(
            "my_database",
            "DATACUT",
            dataset_id_test_dataset,
            "test_dataset",
            table_id,
            "test_dataset",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)
        stdout, stderr, code = await give_user_dataset_perms("test_dataset")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        _, _, _ = await make_all_tools_visible()
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        await ensure_team_created("not-my-team")
        await ensure_team_created("My Team")
        await add_user_to_team("7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2", "My Team")

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("Tool with DB access is loading...", application_content_1)

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_2 = await response.text()

        self.assertIn("Tool with DB access is loading...", application_content_2)

        await until_non_202(session, "http://testdbapplication-23b40dd9.dataworkspace.test:8000/")

        # Check we go wrong when we have no table
        table = uuid.uuid4().hex
        async with session.request(
            "GET",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_user_23b40dd9/{table}",
        ) as response:
            received_status = response.status
            content = await response.text()
        self.assertEqual(received_status, 500)
        self.assertEqual(content, "500 Internal Server Error\n\nServer got itself in trouble")

        # Make the table in the private schema
        async with session.request(
            "POST",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_user_23b40dd9/{table}",
        ) as response:
            received_status = response.status
            await response.text()
        self.assertEqual(received_status, 200)

        # Fetch everything from the table in the private schema
        async with session.request(
            "GET",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_user_23b40dd9/{table}",
        ) as response:
            received_status = response.status
            content = await response.text()
        self.assertEqual(received_status, 200)
        self.assertEqual(json.loads(content), {"data": [[1, "orange"]]})

        # Make the table in the team schema
        team_table = uuid.uuid4().hex
        async with session.request(
            "POST",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_team_my_team/{team_table}",
        ) as response:
            received_status = response.status
            await response.text()
        self.assertEqual(received_status, 200)

        # Get data from the team schema table
        async with session.request(
            "GET",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_team_my_team/{team_table}",
        ) as response:
            received_status = response.status
            content = await response.text()
        self.assertEqual(received_status, 200)
        self.assertEqual(json.loads(content), {"data": [[1, "orange"]]})

        # Ensure we cannot make a table in another team's schema
        another_team_table = uuid.uuid4().hex
        async with session.request(
            "POST",
            f"http://testdbapplication-23b40dd9.dataworkspace.test:8000/my_database/_team_not_my_team/{another_team_table}",
        ) as response:
            received_status = response.status
            await response.text()
        self.assertEqual(received_status, 500)

        # Stop the application
        async with session.request(
            "POST", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/stop"
        ) as response:
            await response.text()

    @async_test
    async def test_visualisation_shows_content_if_authorized_and_published(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        stdout, stderr, code = await create_visualisation_echo("testvisualisation")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # Ensure the user doesn't see the visualisation link on the home page
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            content = await response.text()
        self.assertNotIn("Test testvisualisation", content)

        # Ensure the user doesn't have access to the application
        async with session.request(
            "GET", "http://testvisualisation.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # Ensure that the user can't see a visualisation which is published if they don't have authorization
        stdout, stderr, code = await toggle_visualisation_visibility(
            "testvisualisation", visible=True
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # Ensure the user doesn't have access to the application
        async with session.request(
            "GET", "http://testvisualisation.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # Ensure that the user can't see a visualisation which is unpublished, even if if they have authorization
        stdout, stderr, code = await give_user_visualisation_perms("testvisualisation")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)
        stdout, stderr, code = await toggle_visualisation_visibility(
            "testvisualisation", visible=False
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # Ensure the user doesn't have access to the application
        async with session.request(
            "GET", "http://testvisualisation.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # Finally, if the visualisation is published *and* they have authorization, they can see it.
        stdout, stderr, code = await toggle_visualisation_visibility(
            "testvisualisation", visible=True
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://testvisualisation.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("testvisualisation is loading...", application_content_1)

        await until_non_202(session, "http://testvisualisation.dataworkspace.test:8000/")

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "GET",
            "http://testvisualisation.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_content["headers"]["sso-profile-email"], "test@test.com")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        stdout, stderr, code = await set_visualisation_wrap(
            "testvisualisation", "FULL_HEIGHT_IFRAME"
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://testvisualisation.dataworkspace.test:8000/",
            headers=sent_headers,
        ) as response:
            received_content = await response.text()

        self.assertIn(
            '<iframe src="http://testvisualisation--8888.dataworkspace.test:8000/"',
            received_content,
        )

        async with session.request(
            "GET",
            "http://testvisualisation--8888.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

    @async_test
    async def test_visualisation_commit_shows_content_if_authorized(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        stdout, stderr, code = await create_visualisation_echo("testvisualisation")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        def handle_users(request):
            return web.json_response([{"id": 1234}], status=200)

        project = {
            "id": 3,
            "name": "testvisualisation",
            "tag_list": ["visualisation"],
            "default_branch": "my-default-3",
            "description": "The vis",
            "web_url": "https://some.domain.test/",
        }

        def handle_project(request):
            return web.json_response(project)

        access_level = 20

        def handle_members(request):
            return web.json_response([{"id": 1234, "access_level": access_level}], status=200)

        def handle_general_gitlab(request):
            return web.json_response({})

        gitlab_cleanup = await create_server(
            8007,
            [
                web.get("/api/v4/users", handle_users),
                web.get("/api/v4/projects/3/members/all", handle_members),
                web.get("/api/v4/projects/3", handle_project),
                web.get("/{path:.*}", handle_general_gitlab),
            ],
        )
        self.add_async_cleanup(gitlab_cleanup)

        # Ensure the user doesn't have access to the application
        async with session.request(
            "GET", "http://testvisualisation--11372717.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        access_level = 30

        async with session.request(
            "GET", "http://testvisualisation--11372717.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("testvisualisation [11372717]", application_content_1)
        self.assertIn("is loading...", application_content_1)

        await until_non_202(session, "http://testvisualisation--11372717.dataworkspace.test:8000/")

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "GET",
            "http://testvisualisation--11372717.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        async with session.request(
            "GET",
            "http://testvisualisation--11372717--8888.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

    @async_test
    async def test_visualisation_shows_dataset_if_authorised(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure user created
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        dataset_id_test_dataset = "70ce6fdd-1791-4806-bbe0-4cf880a9cc37"
        table_id = "5a2ee5dd-f025-4939-b0a1-bb85ab7504d7"
        stdout, stderr, code = await create_private_dataset(
            "my_database",
            "MASTER",
            dataset_id_test_dataset,
            "test_dataset",
            table_id,
            "test_dataset",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        dataset_id_dataset_1 = "0dea6147-d355-4b6d-a140-0304ef9cfeca"
        table_id = "39e3fa48-9352-471a-b278-3eca5ba92921"
        stdout, stderr, code = await create_private_dataset(
            "test_external_db",
            "MASTER",
            dataset_id_dataset_1,
            "dataset_1",
            table_id,
            "dataset_1",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
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

        stdout, stderr, code = await create_visualisation_dataset("testvisualisation-a", 3)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms("testvisualisation-a")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        def handle_users(request):
            return web.json_response([{"id": 1234}], status=200)

        def handle_project_3(request):
            return web.json_response(
                {
                    "id": 3,
                    "name": "testvisualisation",
                    "tag_list": ["visualisation"],
                    "default_branch": "master",
                    "description": "The vis",
                    "web_url": "https://some.domain.test/",
                }
            )

        def handle_project_4(request):
            return web.json_response(
                {
                    "id": 4,
                    "name": "testvisualisation",
                    "tag_list": ["visualisation"],
                    "default_branch": "master",
                    "description": "The vis",
                    "web_url": "https://some.domain.test/",
                }
            )

        def handle_members(request):
            return web.json_response([{"id": 1234, "access_level": 30}], status=200)

        def handle_general_gitlab(request):
            return web.json_response({})

        gitlab_cleanup = await create_server(
            8007,
            [
                web.get("/api/v4/users", handle_users),
                web.get("/api/v4/projects/3/members/all", handle_members),
                web.get("/api/v4/projects/3", handle_project_3),
                web.get("/api/v4/projects/4/members/all", handle_members),
                web.get("/api/v4/projects/4", handle_project_4),
                web.get("/{path:.*}", handle_general_gitlab),
            ],
        )
        self.add_async_cleanup(gitlab_cleanup)

        stdout, stderr, code = await give_user_dataset_perms("dataset_1")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/datasets"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(403, status)

        await give_user_visualisation_developer_perms()

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/datasets"
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 200)
        csrf_token = re.match(
            r".*name=\"csrfmiddlewaretoken\"\svalue=\"([^\"]+)\".*",
            content,
            flags=re.DOTALL,
        )[1]

        # The user only has access dataset_2, not dataset_1: we test that
        # a user cannot add access to a dataset they don't have access to
        async with session.request(
            "POST",
            "http://dataworkspace.test:8000/visualisations/3/datasets",
            data=(
                ("dataset", dataset_id_dataset_2),
                ("dataset", dataset_id_dataset_1),
                ("csrfmiddlewaretoken", csrf_token),
            ),
        ) as response:
            received_status = response.status
            await response.text()

        self.assertEqual(received_status, 200)

        async with session.request(
            "GET", "http://testvisualisation-a.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("testvisualisation-a is loading...", application_content_1)

        await until_non_202(session, "http://testvisualisation-a.dataworkspace.test:8000/")

        async with session.request(
            "GET",
            "http://testvisualisation-a.dataworkspace.test:8000/my_database/test_dataset",
        ) as response:
            received_status = response.status
            content = await response.text()

        # This application should not have permission to access the database,
        # and we get a simple 500 page from the visualisation in this case
        self.assertEqual(received_status, 500)
        self.assertEqual(content, "500 Internal Server Error\n\nServer got itself in trouble")

        async with session.request(
            "GET",
            "http://testvisualisation-a.dataworkspace.test:8000/test_external_db2/dataset_2",
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 500)
        self.assertEqual(content, "500 Internal Server Error\n\nServer got itself in trouble")

        async with session.request(
            "GET",
            "http://testvisualisation-a.dataworkspace.test:8000/test_external_db/dataset_1",
        ) as response:
            received_status = response.status
            content = await response.json()

        self.assertEqual(content, {"data": [1, 2]})

        # Stop the application
        async with session.request(
            "POST", "http://testvisualisation-a.dataworkspace.test:8000/stop"
        ) as response:
            await response.text()

        # The first request after an application stopped unexpectedly should
        # be an error
        async with session.request(
            "GET", "http://testvisualisation-a.dataworkspace.test:8000/"
        ) as response:
            content = await response.text()
        self.assertIn("Sorry, there is a problem with the service", content)

        # Give the visualisation permission to a dataset that the user
        # doesn't have access to.
        stdout, stderr, code = await give_visualisation_dataset_perms(
            "testvisualisation-a", "dataset_2"
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/datasets"
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 200)
        csrf_token = re.match(
            r".*name=\"csrfmiddlewaretoken\"\svalue=\"([^\"]+)\".*",
            content,
            flags=re.DOTALL,
        )[1]

        # No datasets posted, i.e. attempting to removing access from all datasets
        async with session.request(
            "POST",
            "http://dataworkspace.test:8000/visualisations/3/datasets",
            data=(("csrfmiddlewaretoken", csrf_token),),
        ) as response:
            received_status = response.status
            await response.text()

        async with session.request(
            "GET", "http://testvisualisation-a.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("testvisualisation-a is loading...", application_content_1)

        await until_non_202(session, "http://testvisualisation-a.dataworkspace.test:8000/")

        # The application does have access to the dataset that the user does
        # not have access to, even though user tried to remove it
        async with session.request(
            "GET",
            "http://testvisualisation-a.dataworkspace.test:8000/test_external_db2/dataset_2",
        ) as response:
            received_status = response.status
            content = await response.json()

        self.assertEqual(content, {"data": [1, 2]})

        # The application now does not have access to the dataset that the
        # user removed
        async with session.request(
            "GET",
            "http://testvisualisation-a.dataworkspace.test:8000/test_external_db/dataset_1",
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 500)
        self.assertEqual(content, "500 Internal Server Error\n\nServer got itself in trouble")

        # Stop the application
        async with session.request(
            "POST", "http://testvisualisation-a.dataworkspace.test:8000/stop"
        ) as response:
            await response.text()

        stdout, stderr, code = await create_visualisation_dataset("testvisualisation-b", 4)
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms("testvisualisation-b")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/4/datasets"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(200, status)
        self.assertNotIn("test_dataset", content)

        stdout, stderr, code = await give_visualisation_dataset_perms(
            "testvisualisation-b", "test_dataset"
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/4/datasets"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertIn("test_dataset", content)

        async with session.request(
            "GET", "http://testvisualisation-b.dataworkspace.test:8000/"
        ) as response:
            application_content_2 = await response.text()

        self.assertIn("testvisualisation-b is loading...", application_content_2)

        await until_non_202(session, "http://testvisualisation-b.dataworkspace.test:8000/")

        async with session.request(
            "GET",
            "http://testvisualisation-b.dataworkspace.test:8000/my_database/test_dataset",
        ) as response:
            received_status = response.status
            received_content = await response.json()

        self.assertEqual(received_content, {"data": list(range(1, 20001))})
        self.assertEqual(received_status, 200)

    @async_test
    async def test_application_spawn(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Make a request to the home page, which ensures the user is in the DB
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        await asyncio.sleep(1)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/",
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("Test Application is loading...", application_content_1)

        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_2 = await response.text()

        self.assertIn("Test Application is loading...", application_content_2)

        await until_non_202(session, "http://testapplication-23b40dd9.dataworkspace.test:8000/")

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {"from-downstream": "downstream-header-value"}

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "GET")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        # We are authorized by SSO, and can do non-GETs
        async def sent_content():
            for _ in range(10000):
                yield b"Some content"

        sent_headers = {"from-downstream": "downstream-header-value"}
        async with session.request(
            "PATCH",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            data=sent_content(),
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content["method"], "PATCH")
        self.assertEqual(received_content["headers"]["from-downstream"], "downstream-header-value")
        self.assertEqual(received_content["content"], "Some content" * 10000)
        self.assertEqual(received_headers["from-upstream"], "upstream-header-value")

        # Make a websockets connection to the proxy
        sent_headers = {"from-downstream-websockets": "websockets-header-value"}
        async with session.ws_connect(
            "http://testapplication-23b40dd9.dataworkspace.test:8000/websockets",
            headers=sent_headers,
        ) as wsock:
            msg = await wsock.receive()
            headers = json.loads(msg.data)

            await wsock.send_bytes(b"some-\0binary-data")
            msg = await wsock.receive()
            received_binary_content = msg.data

            await wsock.send_str("some-text-data")
            msg = await wsock.receive()
            received_text_content = msg.data

            await wsock.close()

        self.assertEqual(headers["from-downstream-websockets"], "websockets-header-value")
        self.assertEqual(received_binary_content, b"some-\0binary-data")
        self.assertEqual(received_text_content, "some-text-data")

    @async_test
    async def test_application_redirects_to_sso_if_initially_not_authorized(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        is_logged_in = False
        codes = iter([])
        tokens = iter([])
        auth_to_me = {}
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Make a request to the application home page
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn("This is the login page", content)

        # Make a request to the application admin page
        async with session.request("GET", "http://dataworkspace.test:8000/admin") as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn("This is the login page", content)
