# pylint: disable=not-async-context-manager
import unittest

import asyncio

from test.utility_functions import (
    client_session,
    create_application,
    create_private_dataset,
    create_sentry,
    create_sso,
    create_superset,
    create_visusalisation,
    flush_database,
    flush_redis,
    give_user_app_perms,
    give_user_dataset_perms,
    until_succeeds,
)


class TestApplication(unittest.IsolatedAsyncioTestCase):
    async def test_application_shows_forbidden_if_not_auth_ip(self):
        await flush_database()
        await flush_redis()

        cleanup_sentry, sentry_requests = await create_sentry()
        self.addAsyncCleanup(cleanup_sentry)

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        # Create application with a non-open whitelist
        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__1": "4.3.1.1/32",
            }
        )
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(
            [
                "some-code-1",
                "some-code-2",
                "some-code-3",
                "some-code-4",
                "some-code-5",
                "some-code-6",
            ]
        )
        tokens = iter(["token-1", "token-1", "token-1", "token-1", "token-1", "token-1"])
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

        # Make a request to the home page, which creates the user...
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        # ... with application permissions...
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # ... and can make requests to the home page...
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            content = await response.text()
        self.assertNotIn("You do not have access to this page", content)
        self.assertEqual(response.status, 200)

        # ... but not the application...
        async with session.request(
            "GET", "http://testapplication-23b40dd9.dataworkspace.test:8000/http"
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # ... and it can't be spoofed...
        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)
        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "4.3.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        await cleanup_application()

        # ... but that X_FORWARDED_FOR_TRUSTED_HOPS and subnets are respected
        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_WHITELIST__2": "5.0.0.0/8",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__1": "4.3.1.1/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__2": "3.0.0.0/8",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
                "SENTRY_DSN": "http://foobar@localhost:8009/123",
                "SENTRY_ENVIRONMENT": "Test",
            }
        )
        self.addAsyncCleanup(cleanup_application)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        # Starting the application is asynchronous, with the proxy component starting up faster
        # than the Django application. So initial calls to the healthcheck fail at the proxy ->
        # Django phase, which cause the proxy to log exceptions to (the fake) Sentry. We wait for
        # these exceptions to make it to Sentry, and then clear our log of them so we can assert
        # on the ones deliberately sent later on in this test.
        await asyncio.sleep(1)
        sentry_requests.clear()

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("Test Application is loading...", content)
        self.assertEqual(response.status, 202)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "6.5.4.3, 1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("Test Application is loading...", content)
        self.assertEqual(response.status, 202)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "5.1.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Test Application is loading...", content)
        self.assertEqual(response.status, 202)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "3.1.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Test Application is loading...", content)
        self.assertEqual(response.status, 202)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "6.5.4.3"},
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/http",
            headers={"x-forwarded-for": "1.2.3.4, 6.5.4.3"},
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # The healthcheck is allowed from a private IP: simulates ALB
        async with session.request(
            "GET", "http://dataworkspace.test:8000/healthcheck"
        ) as response:
            content = await response.text()

        self.assertEqual("OK", content)
        self.assertEqual(response.status, 200)

        # ... and from a publically routable one: simulates Pingdom
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/healthcheck",
            headers={"x-forwarded-for": "8.8.8.8"},
        ) as response:
            content = await response.text()

        self.assertEqual("OK", content)
        self.assertEqual(response.status, 200)

        # ... but not allowed to get to the application
        assert len(sentry_requests) == 0
        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/healthcheck",
            headers={},
        ) as response:
            content = await response.text()

        # In production, hitting this URL without X-Forwarded-For should not
        # be possible, so a 500 is most appropriate
        self.assertEqual(response.status, 500)

        # Check that sentry is reporting on 500s - the short sleep gives the lib enough time to fire it off.
        await asyncio.sleep(1)
        assert len(sentry_requests) == 1

        async with session.request(
            "GET",
            "http://testapplication-23b40dd9.dataworkspace.test:8000/healthcheck",
            headers={"x-forwarded-for": "8.8.8.8"},
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

    async def test_integrated_data_explorer_has_ip_restrictions(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        # Create application with a non-open whitelist
        # Explorer/DB credentials generator cannot handle two database connections which point to the sme
        # database instance (as it will try to create the user in "each" database and the second will throw an error
        # because the user already exists.
        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__1": "4.3.1.1/32",
                "EXPLORER_CONNECTIONS": '{"Postgres": "my_database"}',
            }
        )
        self.addAsyncCleanup(cleanup_application)

        is_logged_in = True
        codes = iter(
            [
                "some-code-1",
                "some-code-2",
                "some-code-3",
                "some-code-4",
                "some-code-5",
                "some-code-6",
                "some-code-7",
                "some-code-8",
            ]
        )
        tokens = iter(
            [
                "token-1",
                "token-1",
                "token-1",
                "token-1",
                "token-1",
                "token-1",
                "token-1",
                "token-1",
            ]
        )
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

        # Make a request to the home page, which creates the user...
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            await response.text()

        # ... with application permissions...
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        # ... and can make requests to the home page...
        async with session.request("GET", "http://dataworkspace.test:8000/") as response:
            content = await response.text()
        self.assertNotIn("You do not have access to this page", content)
        self.assertEqual(response.status, 200)

        # ... but not data explorer...
        async with session.request(
            "GET", "http://dataworkspace.test:8000/data-explorer/"
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        # ... and it can't be spoofed...
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "4.3.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

        await cleanup_application()

        # ... but that X_FORWARDED_FOR_TRUSTED_HOPS and subnets are respected
        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_WHITELIST__2": "5.0.0.0/8",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__1": "4.3.1.1/32",
                "APPLICATION_IP_ALLOWLIST_GROUPS__my_group__2": "3.0.0.0/8",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
                "EXPLORER_CONNECTIONS": '{"Postgres": "my_database"}',
            }
        )
        self.addAsyncCleanup(cleanup_application)

        await until_succeeds("http://dataworkspace.test:8000/healthcheck")

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "4.3.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "6.5.4.3, 1.2.3.4"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "6.5.4.3, 4.3.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "5.1.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)
        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "3.1.1.1"},
        ) as response:
            content = await response.text()
        self.assertIn("Welcome to Data Explorer", content)
        self.assertEqual(response.status, 200)

        async with session.request(
            "GET",
            "http://dataworkspace.test:8000/data-explorer/",
            headers={"x-forwarded-for": "6.5.4.3"},
        ) as response:
            content = await response.text()

        self.assertIn("You do not have access to this page", content)
        self.assertEqual(response.status, 403)

    async def test_superset_editor_headers(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_superset, superset_requests = await create_superset()
        self.addAsyncCleanup(cleanup_superset)

        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_WHITELIST__2": "5.0.0.0/8",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
                "SUPERSET_ROOT": "http://localhost:8008/",
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

        stdout, stderr, code = await give_user_dataset_perms("test_dataset")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await create_visusalisation(
            "test_visualisation", "REQUIRES_AUTHENTICATION", "SUPERSET", 1
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://superset-edit.dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            self.assertEqual(response.status, 200)

        assert superset_requests[0].headers["Credentials-Memorable-Name"] == "my_database"
        assert superset_requests[0].headers["Credentials-Db-Name"] == "datasets"
        assert superset_requests[0].headers["Credentials-Db-Host"] == "data-workspace-postgres"
        assert superset_requests[0].headers["Credentials-Db-Port"] == "5432"
        assert superset_requests[0].headers["Credentials-Db-Persistent-Role"] == "_user_23b40dd9"
        assert (
            superset_requests[0].headers["Credentials-Db-User"].startswith("user_test_test_com_")
        )
        assert superset_requests[0].headers["Credentials-Db-User"].endswith("superset")
        assert "Credentials-Db-Password" in superset_requests[0].headers

    async def test_superset_public_headers(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.addAsyncCleanup(cleanup_session)

        cleanup_superset, superset_requests = await create_superset()
        self.addAsyncCleanup(cleanup_superset)

        cleanup_application = await create_application(
            env=lambda: {
                "APPLICATION_IP_WHITELIST__1": "1.2.3.4/32",
                "APPLICATION_IP_WHITELIST__2": "5.0.0.0/8",
                "X_FORWARDED_FOR_TRUSTED_HOPS": "2",
                "SUPERSET_ROOT": "http://localhost:8008/",
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

        stdout, stderr, code = await give_user_dataset_perms("test_dataset")
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        stdout, stderr, code = await create_visusalisation(
            "test_visualisation", "REQUIRES_AUTHENTICATION", "SUPERSET", 1
        )
        self.assertEqual(stdout, b"")
        self.assertEqual(stderr, b"")
        self.assertEqual(code, 0)

        async with session.request(
            "GET",
            "http://superset.dataworkspace.test:8000/",
            headers={"x-forwarded-for": "1.2.3.4"},
        ) as response:
            self.assertEqual(response.status, 200)

        assert superset_requests[0].headers["Credentials-Memorable-Name"] == "my_database"
        assert superset_requests[0].headers["Credentials-Db-Name"] == "datasets"
        assert superset_requests[0].headers["Credentials-Db-Host"] == "data-workspace-postgres"
        assert superset_requests[0].headers["Credentials-Db-Port"] == "5432"
        assert superset_requests[0].headers["Credentials-Db-User"] == "postgres"
        assert superset_requests[0].headers["Credentials-Db-Password"] == "postgres"
        assert superset_requests[0].headers["Dashboards"] == "1"
