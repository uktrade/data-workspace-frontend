# pylint: disable=not-async-context-manager
import csv
import io
import json
import os
import unittest

from test.utility_functions import (
    add_user_to_mlflow_instance,
    b64_decode,
    client_session,
    create_application,
    create_application_db_user,
    create_metadata_table,
    create_mirror,
    create_mlflow,
    create_private_dataset,
    create_sample_datasets_and_visualisations,
    create_sentry,
    create_server,
    create_sso,
    create_query_logs,
    find_search_filter_labels,
    flush_database,
    flush_redis,
    give_user_app_perms,
    give_user_dataset_perms,
    give_user_visualisation_developer_perms,
    sync_query_logs,
    until_succeeds,
    until_non_202,
    ensure_arango_team_created,
    add_user_to_arango_team,
)

from aiohttp import web
import aiopg
import mohawk

from test.pages import (  # pylint: disable=wrong-import-order
    DataCataloguePage,
    get_browser,
)


class TestApplication(unittest.IsolatedAsyncioTestCase):
    async def test_application_redirects_to_sso_if_different_ip_group(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group_a__1": "4.3.1.1/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group_a__2": "4.3.1.2/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group_b__1": "5.3.1.1/32",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
            }
        )
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code-1", "some-code-2", "some-code-3"])
        tokens = iter(["token-1", "token-1", "token-1"])
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
        sso_cleanup, number_of_times_at_sso = await create_sso(
            is_logged_in, codes, tokens, auth_to_me
        )
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # In first IP group
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "4.3.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 1)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "4.3.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 1)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "4.3.1.2"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 1)

        # In second IP group
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "5.3.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 2)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "5.3.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 2)

        # Not in any IP group, but still fine to home page is not behind filter
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.1.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 3)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.1.1.1"},
        ) as response:
            self.assertEqual(200, response.status)
            self.assertEqual(number_of_times_at_sso(), 3)

    async def test_application_download(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code", "some-other-code"])
        tokens = iter(["token-1", "token-2"])
        auth_to_me = {
            # No token-1
            "Bearer token-2": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        dataset_id_test_dataset = "70ce6fdd-1791-4806-bbe0-4cf880a9cc37"
        table_id = "5a2ee5dd-f025-4939-b0a1-bb85ab7504d7"

        stdout, stderr, code = await create_metadata_table()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

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

        async with session.request(
            "GET", f"http://dataworkspace.test:8000/datasets/{dataset_id_test_dataset}"
        ) as response:
            content = await response.text()

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/table_data/my_database/public/test_dataset",
        ) as response:
            content = await response.text()
            status = response.status

        self.assertEqual(status, 403)
        self.assertEqual(content, "")

        stdout, stderr, code = await give_user_dataset_perms("test_dataset")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/datasets/70ce6fdd-1791-4806-bbe0-4cf880a9cc37",
        ) as response:
            content = await response.text()

        self.assertNotIn("You need to request access to view these links", content)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/table_data/my_database/public/test_dataset",
        ) as response:
            content = await response.text()

        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(rows[0], ["id", "data"])
        self.assertEqual(rows[1][1], "test data 1")
        self.assertEqual(rows[2][1], "test data 2")
        self.assertEqual(rows[20001][0], "Number of rows: 20000")

        async def fetch_num_connections():
            pool = await aiopg.create_pool(
                "dbname=dataworkspace user=postgres password=postgres "
                "host=data-workspace-postgres"
            )
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT numbackends FROM pg_stat_database WHERE datname='dataworkspace'"
                    )
                    return [row[0] for row in await cur.fetchall()][0]

        # We ensure that multiple parallel downloads, that were not initiated
        # in parallel, do not use another database connection to the main
        # Django database
        num_connections_1 = await fetch_num_connections()
        response_1 = await session.request(
            "GET",
            "http://dataworkspace.test:8000/table_data/my_database/public/test_dataset",
        )
        num_connections_2 = await fetch_num_connections()
        response_2 = await session.request(
            "GET",
            "http://dataworkspace.test:8000/table_data/my_database/public/test_dataset",
        )
        num_connections_3 = await fetch_num_connections()
        response_3 = await session.request(
            "GET",
            "http://dataworkspace.test:8000/table_data/my_database/public/test_dataset",
        )
        num_connections_4 = await fetch_num_connections()

        # We should only have two connections: one from the application,
        # and one from the connection querying the number of connections
        self.assertEqual(num_connections_1, 2)
        self.assertEqual(num_connections_2, 2)
        self.assertEqual(num_connections_3, 2)
        self.assertEqual(num_connections_4, 2)

        rows_1 = list(csv.reader(io.StringIO(await response_1.text())))
        rows_2 = list(csv.reader(io.StringIO(await response_2.text())))
        rows_3 = list(csv.reader(io.StringIO(await response_3.text())))

        self.assertEqual(rows_1[20001][0], "Number of rows: 20000")
        self.assertEqual(rows_2[20001][0], "Number of rows: 20000")
        self.assertEqual(rows_3[20001][0], "Number of rows: 20000")

    async def test_hawk_authenticated_source_table_api_endpoint(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code", "some-other-code"])
        tokens = iter(["token-1", "token-2"])
        auth_to_me = {
            # No token-1
            "Bearer token-2": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Check that with no authorization header there is no access
        dataset_id = "70ce6fdd-1791-4806-bbe0-4cf880a9cc37"
        table_id = "5a2ee5dd-f025-4939-b0a1-bb85ab7504d7"
        url = f"http://dataworkspace.test:8000/api/v1/dataset/{dataset_id}/{table_id}"
        stdout, stderr, code = await create_private_dataset(
            "my_database",
            "MASTER",
            dataset_id,
            "test_dataset",
            table_id,
            "test_dataset",
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request("GET", url) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

        # unauthenticated request
        client_id = os.environ["HAWK_SENDERS__1__id"]
        client_key = "incorrect_key"
        algorithm = os.environ["HAWK_SENDERS__1__algorithm"]
        method = "GET"
        content = ""
        content_type = ""
        credentials = {"id": client_id, "key": client_key, "algorithm": algorithm}
        sender = mohawk.Sender(
            credentials=credentials,
            url=url,
            method=method,
            content=content,
            content_type=content_type,
        )
        headers = {"Authorization": sender.request_header, "Content-Type": content_type}

        async with session.request("GET", url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

        # authenticated request
        client_id = os.environ["HAWK_SENDERS__1__id"]
        client_key = os.environ["HAWK_SENDERS__1__key"]
        algorithm = os.environ["HAWK_SENDERS__1__algorithm"]
        method = "GET"
        content = ""
        content_type = ""
        credentials = {"id": client_id, "key": client_key, "algorithm": algorithm}
        sender = mohawk.Sender(
            credentials=credentials,
            url=url,
            method=method,
            content=content,
            content_type=content_type,
        )
        headers = {"Authorization": sender.request_header, "Content-Type": content_type}

        async with session.request("GET", url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)

        # replay attack
        async with session.request("GET", url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

    async def test_mirror(self):
        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code", "some-other-code"])
        tokens = iter(["token-1", "token-2"])
        auth_to_me = {
            # No token-1
            "Bearer token-2": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.addAsyncCleanup(sso_cleanup)

        mirror_cleanup = await create_mirror()
        self.addAsyncCleanup(mirror_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        async with session.request(
            "GET",
            "http://testvisualisation--11372717.dataworkspace.test:8000/__mirror/some/path/in/mirror",
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        self.assertEqual(content, "Mirror path: /some-remote-folder/some/path/in/mirror")

    async def test_gitlab_application_can_be_managed(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code", "some-other-code"])
        tokens = iter(["token-1", "token-2"])
        auth_to_me = {
            "Bearer token-2": {
                "email": "test@test.com",
                "contact_email": "test@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations"
        ) as response:
            status = response.status
        self.assertEqual(status, 403)

        await give_user_visualisation_developer_perms()

        def handle_group(request):
            return web.json_response({"web_url": "https://some.domain.test/"}, status=200)

        users_query = {}

        def handle_users(request):
            nonlocal users_query
            users_query = request.query
            return web.json_response([{"id": 1234}], status=200)

        project = {
            "id": 3,
            "name": "Michal's Vis_ualisat-tion---",
            "tag_list": ["visualisation"],
            "default_branch": "my-default-3",
            "description": "The vis",
            "web_url": "https://some.domain.test/",
        }
        projects_query = {}

        def handle_projects(request):
            nonlocal projects_query
            projects_query = request.query
            return web.json_response(
                [
                    {
                        "id": 1,
                        "name": "not-a-vis",
                        "tag_list": ["some-tag"],
                        "default_branch": "my-default-1",
                    },
                    {
                        "id": 2,
                        "name": "is-a-vis",
                        "tag_list": ["visualisation"],
                        "default_branch": "my-default-2",
                    },
                    project,
                ],
                status=200,
            )

        def handle_project(request):
            return web.json_response(project)

        access_level = 30

        def handle_members(request):
            return web.json_response([{"id": 1234, "access_level": access_level}], status=200)

        def handle_branches(request):
            return web.json_response(
                [
                    {
                        "name": "my-default-3",
                        "commit": {
                            "id": "some-id",
                            "short_id": "abcdef12",
                            "committed_date": "2015-01-01T01:01:01.000Z",
                        },
                    },
                    {
                        "name": "feature/my-feature-3",
                        "commit": {
                            "id": "some-id",
                            "short_id": "abcdef12",
                            "committed_date": "2015-01-01T01:01:01.000Z",
                        },
                    },
                ],
                status=200,
            )

        def handle_general_gitlab(request):
            return web.json_response({})

        gitlab_cleanup = await create_server(
            8007,
            [
                web.get("/api/v4/groups/visualisations", handle_group),
                web.get("/api/v4/users", handle_users),
                web.get("/api/v4/projects", handle_projects),
                web.get("/api/v4/projects/3/members/all", handle_members),
                web.get("/api/v4/projects/3", handle_project),
                web.get("/api/v4/projects/3/repository/branches", handle_branches),
                web.get("/{path:.*}", handle_general_gitlab),
            ],
        )
        self.addAsyncCleanup(gitlab_cleanup)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations"
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)

        self.assertEqual(users_query["extern_uid"], "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        self.assertEqual(projects_query["sudo"], "1234")
        self.assertNotIn("not-a-vis", content)
        self.assertIn("is-a-vis", content)

        access_level = 20
        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/users/give-access"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 403)
        self.assertNotIn("Give access", content)

        access_level = 30
        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/users/give-access"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn("Give access", content)

        def handle_general_ecr(request):
            return web.json_response(
                {"imageDetails": [{"imageTags": ["michals-vis-ualisat-tion--abcdef12"]}]}
            )

        ecr_cleanup = await create_server(8008, [web.post("/{path:.*}", handle_general_ecr)])
        self.addAsyncCleanup(ecr_cleanup)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/visualisations/3/branches/my-default-3",
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn("Production: abcdef12", content)

        self.assertIn('href="http://michals-vis-ualisat-tion.dataworkspace.test:8000/', content)
        self.assertIn(
            'href="http://michals-vis-ualisat-tion--abcdef12.dataworkspace.test:8000/',
            content,
        )

        # Check that the access level must have been cached
        access_level = 20
        async with session.request(
            "GET", "http://dataworkspace.test:8000/visualisations/3/users/give-access"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn("Give access", content)

    async def test_sentry_dsn_does_not_stop_proxy_from_becoming_healthy(self):
        _, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_sentry, _ = await create_sentry()
        self.addAsyncCleanup(cleanup_sentry)

        cleanup_application = await create_application(
            env=lambda: {
                "SENTRY_DSN": "http://foobar@localhost:8009/123",
                "SENTRY_ENVIRONMENT": "Test",
            }
        )
        self.addAsyncCleanup(cleanup_application)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

    async def test_search_filter_result_predictions(self):
        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

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
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        _, _, code = await create_sample_datasets_and_visualisations()
        assert code == 0

        browser = await get_browser()
        self.addAsyncCleanup(browser.close)
        home_page = await DataCataloguePage(browser=browser).open()

        with_no_filters = find_search_filter_labels(await home_page.get_html())

        assert "Data I have access to (4)" in with_no_filters
        assert "Source dataset (2)" in with_no_filters
        assert "Visualisation (1)" in with_no_filters
        assert "DIT (1)" in with_no_filters
        assert "ONS (1)" in with_no_filters
        assert "HMRC (1)" in with_no_filters

        # Toggle the master dataset filter on (filters: master)
        await home_page.toggle_filter("Source dataset")

        with_master_filter = find_search_filter_labels(await home_page.get_html())
        assert "Data I have access to (1)" in with_master_filter
        assert "Source dataset (2)" in with_master_filter
        assert "Visualisation (1)" in with_master_filter
        assert "DIT (1)" in with_master_filter
        assert not any(f.startswith("ONS") for f in with_master_filter)
        assert "HMRC (1)" in with_master_filter

        # Toggle the reference dataset data type filter on (filters: master, datacut)
        await home_page.toggle_filter("Data cut")

        with_master_and_datacut_filters = find_search_filter_labels(await home_page.get_html())
        assert "Data I have access to (2)" in with_master_and_datacut_filters
        assert "Visualisation (1)" in with_master_and_datacut_filters
        assert "Data cut (1)" in with_master_and_datacut_filters
        assert "DIT (1)" in with_master_and_datacut_filters
        assert "ONS (1)" in with_master_and_datacut_filters
        assert "HMRC (1)" in with_master_and_datacut_filters

        # Toggle the master dataset filter back off (filters: datacut)
        await home_page.toggle_filter("Source dataset")

        with_reference_filter = find_search_filter_labels(await home_page.get_html())
        assert "Data I have access to (1)" in with_reference_filter
        assert "Visualisation (1)" in with_reference_filter
        assert "Data cut (1)" in with_master_and_datacut_filters
        assert not any(f.startswith("DIT") for f in with_reference_filter)
        assert "ONS (1)" in with_master_and_datacut_filters
        assert "HMRC (1)" in with_master_and_datacut_filters

        # Toggle the authorization filter on (filters: authorization, reference)
        await home_page.toggle_filter("Reference dataset")

        with_authorization_and_reference_filters = find_search_filter_labels(
            await home_page.get_html()
        )
        assert "Data I have access to (2)" in with_authorization_and_reference_filters
        assert "Visualisation (1)" in with_authorization_and_reference_filters
        assert not any(f.startswith("DIT") for f in with_authorization_and_reference_filters)
        assert "ONS (1)" in with_master_and_datacut_filters
        assert not any(f.startswith("HMRC") for f in with_authorization_and_reference_filters)

        # Toggle the authorization filter off, reference filter off, and the "DIT" source tag on (filters: DIT)
        await home_page.toggle_filter("Reference dataset")
        await home_page.toggle_filter("Data cut")
        await home_page.toggle_filter("DIT")

        with_dit_filter = find_search_filter_labels(await home_page.get_html())
        assert "Data I have access to (1)" in with_dit_filter
        assert "Visualisation (0)" in with_dit_filter
        assert "DIT (1)" in with_dit_filter
        assert "ONS (1)" in with_dit_filter
        assert "HMRC (1)" in with_dit_filter

        # Toggle the "ONS" source tag on (filters: DIT, ONS)
        await home_page.toggle_filter("ONS")

        with_dit_and_ons_filters = find_search_filter_labels(await home_page.get_html())
        assert "Data I have access to (2)" in with_dit_and_ons_filters
        assert "Visualisation (0)" in with_dit_and_ons_filters
        assert "DIT (1)" in with_dit_and_ons_filters
        assert "ONS (1)" in with_dit_and_ons_filters
        assert "HMRC (1)" in with_dit_and_ons_filters

    async def test_tool_query_log_sync(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "peter@test.com",
                "contact_email": "peter@test.com",
                "related_emails": [],
                "first_name": "Peter",
                "last_name": "Piper",
                "user_id": "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2",
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        _, _, code = await create_application_db_user()
        assert code == 0

        _, _, code = await create_query_logs()
        assert code == 0

        _, _, code = await sync_query_logs()
        assert code == 0

        # Initial log in forces redirect to admin homepage
        async with session.request("GET", "http://dataworkspace.test:8000/admin") as response:
            await response.text()
            self.assertEqual(200, response.status)

        async with session.request(
            "GET", "http://dataworkspace.test:8000/admin/datasets/toolqueryauditlog/"
        ) as response:
            content = await response.text()
            self.assertEqual(200, response.status)
            self.assertIn(
                "CREATE TABLE IF NOT EXISTS query_log_test (id INT, name TEXT);",
                content,
            )
            self.assertIn("INSERT INTO query_log_test VALUES(1, &#x27;a record&#x27;);", content)
            self.assertIn("SELECT * FROM query_log_test;", content)

    async def test_sso_token_endpoint_header(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        headers = {}

        async def handle_authorize(request):
            return web.HTTPFound(
                f"{request.query['redirect_uri']}?state={request.query['state']}&code=xxx"
            )

        async def handle_me(_):
            return web.json_response({}, status=403)

        async def handle_token(request):
            nonlocal headers
            headers = request.headers
            return web.json_response({}, status=403)

        sso_app = web.Application()
        sso_app.add_routes(
            [
                web.get("/o/authorize/", handle_authorize),
                web.post("/o/token/", handle_token),
                web.get("/api/v1/user/me/", handle_me),
            ]
        )

        sso_runner = web.AppRunner(sso_app)
        await sso_runner.setup()
        sso_site = web.TCPSite(sso_runner, "0.0.0.0", 8005)
        await sso_site.start()

        async with session.request("GET", "http://dataworkspace.test:8000/"):
            assert (
                "Accept-Encoding" not in headers
            ), "Encoding incorrectly sent to SSO token endpoint"

        await sso_site.stop()

    async def test_mlflow(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_mlflow, mlflow_requests = await create_mlflow()
        self.addAsyncCleanup(cleanup_mlflow)

        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_WHITELIST__2": "5.0.0.0/8",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
                "JWT_PRIVATE_KEY": (
                    "-----BEGIN PRIVATE KEY-----\n"
                    "MC4CAQAwBQYDK2VwBCIEIA/EXAMPLE/EXAMPLE/EXAMPLE/EXAMPLE/EXAMPLE/A\n"
                    "-----END PRIVATE KEY-----\n"
                ),
                "MLFLOW_PORT": "8004",
            }
        )
        self.addAsyncCleanup(cleanup_application)

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
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure user created
        async with session.request(
            "GET", "http://dataworkspace.test:8000/", headers={"x-forwarded-for": "1.2.3.4"}
        ) as response:
            await response.text()

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://mlflow--data-science.dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            self.assertEqual(response.status, 200)

        self.assertTrue("Authorization" in mlflow_requests[0].headers)

        jwt_token = mlflow_requests[0].headers["Authorization"][7:].encode()
        _, payload_b64, _ = jwt_token.split(b".")
        payload = json.loads(b64_decode(payload_b64))

        # User has not been authorised to access an MLflow instance yet so payload should
        # have no authorised hosts
        self.assertEqual(payload["authorised_hosts"], [])

        stdout, stderr, code = await add_user_to_mlflow_instance(
            "7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2", "data-science"
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://mlflow--data-science.dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            self.assertEqual(response.status, 200)

        self.assertTrue("Authorization" in mlflow_requests[1].headers)

        jwt_token = mlflow_requests[1].headers["Authorization"][7:].encode()
        _, payload_b64, _ = jwt_token.split(b".")
        payload = json.loads(b64_decode(payload_b64))

        # User has now been authorised to access the data science MLflow instance so payload
        # should contain an authorised host
        self.assertEqual(
            payload["authorised_hosts"], ["mlflow--data-science--internal.dataworkspace.test:8000"]
        )

    async def test_arango_no_team_permissions(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

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
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure the record has been created
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("Tool with DB access is loading...", application_content_1)

        await until_non_202(session, "http://testdbapplication-23b40dd9.dataworkspace.test:8000/")

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/arango"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertEqual('{"data": "No user credentials."}', content)

    async def test_arango_team_database_permissions(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_application = await create_application()
        self.addAsyncCleanup(cleanup_application)

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
        self.addAsyncCleanup(sso_cleanup)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Ensure the record has been created
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # Create arango team - 'Test1' database with team member access in ArangoDB
        _, _, code = await ensure_arango_team_created(team_name="Test1")
        self.assertEqual(code, 0)
        _, _, code = await add_user_to_arango_team(
            user_sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2", team_name="Test1"
        )
        self.assertEqual(code, 0)

        # Create arango team - 'Test2' database with no access in ArangoDB
        _, _, code = await ensure_arango_team_created(team_name="Test2")
        self.assertEqual(code, 0)

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/"
        ) as response:
            application_content_1 = await response.text()

        self.assertIn("Tool with DB access is loading...", application_content_1)

        await until_non_202(session, "http://testdbapplication-23b40dd9.dataworkspace.test:8000/")

        async with session.request(
            "GET", "http://testdbapplication-23b40dd9.dataworkspace.test:8000/arango"
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertEqual('{"data": {"team_test1": "rw", "team_test2": "none"}}', content)
