import asyncio
import csv
import io
import json
import os
import signal
import textwrap
import unittest

import aiohttp
from aiohttp import web
import aioredis


def async_test(func):
    def wrapper(*args, **kwargs):
        future = func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)

    return wrapper


class TestApplication(unittest.TestCase):
    '''Tests the behaviour of the application, including Proxy
    '''

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
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        # Ensure the user doesn't see the application link since they don't
        # have permission
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()
        self.assertNotIn('Test Application', content)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Make a request to the home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        # Ensure the user sees the link to the application
        self.assertEqual(200, response.status)
        self.assertIn('Test Application</a>', content)

        self.assertIn(
            'href="http://testapplication-23b40dd9.localapps.com:8000/"', content
        )

        # Make a request to the tools page
        async with session.request(
            'GET', 'http://localapps.com:8000/tools/'
        ) as response:
            content = await response.text()

        # Ensure the user sees the link to the application
        self.assertEqual(200, response.status)
        self.assertIn('Test Application</button>', content)

        self.assertIn(
            'action="http://testapplication-23b40dd9.localapps.com:8000/"', content
        )

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('Starting Test Application', application_content_1)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/'
        ) as response:
            application_content_2 = await response.text()

        self.assertIn('Starting Test Application', application_content_2)

        # There are forced sleeps in starting a process
        await asyncio.sleep(6)

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {'from-downstream': 'downstream-header-value'}

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(
            received_content['headers']['from-downstream'], 'downstream-header-value'
        )
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # We are authorized by SSO, and can do non-GETs
        async def sent_content():
            for _ in range(10000):
                yield b'Some content'

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'PATCH',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            data=sent_content(),
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'PATCH')
        self.assertEqual(
            received_content['headers']['from-downstream'], 'downstream-header-value'
        )
        self.assertEqual(received_content['content'], 'Some content' * 10000)
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # Assert that transfer-encoding does not become chunked unnecessarily
        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/http'
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)

        async with session.request(
            'PATCH',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            data=b'1234',
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)
        self.assertEqual(received_content['content'], '1234')

        # Make a websockets connection to the proxy
        sent_headers = {'from-downstream-websockets': 'websockets-header-value'}
        async with session.ws_connect(
            'http://testapplication-23b40dd9.localapps.com:8000/websockets',
            headers=sent_headers,
        ) as wsock:
            msg = await wsock.receive()
            headers = json.loads(msg.data)

            await wsock.send_bytes(b'some-\0binary-data')
            msg = await wsock.receive()
            received_binary_content = msg.data

            await wsock.send_str('some-text-data')
            msg = await wsock.receive()
            received_text_content = msg.data

            await wsock.close()

        self.assertEqual(
            headers['from-downstream-websockets'], 'websockets-header-value'
        )
        self.assertEqual(received_binary_content, b'some-\0binary-data')
        self.assertEqual(received_text_content, 'some-text-data')

        # Test that if we will the application, and restart, we initially
        # see an error that the application stopped, but then after refresh
        # we load up the application succesfully
        await cleanup_application_1()
        cleanup_application_2 = await create_application()
        self.add_async_cleanup(cleanup_application_2)

        await asyncio.sleep(6)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/'
        ) as response:
            error_content = await response.text()

        self.assertIn('Application STOPPED', error_content)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('Starting Test Application', content)
        await asyncio.sleep(6)

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(
            received_content['headers']['from-downstream'], 'downstream-header-value'
        )
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

    @async_test
    async def test_application_custom_cpu_memory(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application_1 = await create_application()
        self.add_async_cleanup(cleanup_application_1)

        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(10)

        # Make a request to the home page, which ensures the user is in the DB
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            await response.text()

        await asyncio.sleep(1)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/',
            params={'__memory_cpu': '1024_2048'},
        ) as response:
            application_content_1 = await response.text()

        self.assertIn(
            'Starting Test Application with 2 CPU and 1 GB of memory',
            application_content_1,
        )

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/'
        ) as response:
            application_content_2 = await response.text()

        self.assertIn(
            'Starting Test Application with 2 CPU and 1 GB of memory',
            application_content_2,
        )

        # There are forced sleeps in starting a process
        await asyncio.sleep(6)

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {'from-downstream': 'downstream-header-value'}

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(
            received_content['headers']['from-downstream'], 'downstream-header-value'
        )
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # We are authorized by SSO, and can do non-GETs
        async def sent_content():
            for _ in range(10000):
                yield b'Some content'

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'PATCH',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            data=sent_content(),
            headers=sent_headers,
        ) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'PATCH')
        self.assertEqual(
            received_content['headers']['from-downstream'], 'downstream-header-value'
        )
        self.assertEqual(received_content['content'], 'Some content' * 10000)
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # Make a websockets connection to the proxy
        sent_headers = {'from-downstream-websockets': 'websockets-header-value'}
        async with session.ws_connect(
            'http://testapplication-23b40dd9.localapps.com:8000/websockets',
            headers=sent_headers,
        ) as wsock:
            msg = await wsock.receive()
            headers = json.loads(msg.data)

            await wsock.send_bytes(b'some-\0binary-data')
            msg = await wsock.receive()
            received_binary_content = msg.data

            await wsock.send_str('some-text-data')
            msg = await wsock.receive()
            received_text_content = msg.data

            await wsock.close()

        self.assertEqual(
            headers['from-downstream-websockets'], 'websockets-header-value'
        )
        self.assertEqual(received_binary_content, b'some-\0binary-data')
        self.assertEqual(received_text_content, 'some-text-data')

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

        await asyncio.sleep(6)

        # Make a request to the application home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

        # Make a request to the application admin page
        async with session.request(
            'GET', 'http://localapps.com:8000/admin'
        ) as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

    @async_test
    async def test_application_shows_forbidden_if_not_auth_ip(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        # Create application with a non-open whitelist
        cleanup_application = await create_application(
            env=lambda: {'APPLICATION_IP_WHITELIST__1': '1.2.3.4/32'}
        )
        self.add_async_cleanup(cleanup_application)

        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        # Make a request to the home page, which creates the user...
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            await response.text()

        # ... with application permissions...
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # ... and can make requests to the home page...
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()
        self.assertNotIn('Forbidden', content)
        self.assertEqual(response.status, 200)

        # ... but not the application...
        async with session.request(
            'GET', 'http://testapplication-23b40dd9.localapps.com:8000/http'
        ) as response:
            content = await response.text()
        self.assertIn('Forbidden', content)
        self.assertEqual(response.status, 403)

        # ... and it can't be spoofed...
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('Forbidden', content)
        self.assertEqual(response.status, 403)

        await cleanup_application()

        # ... but that X_FORWARDED_FOR_TRUSTED_HOPS and subnets are respected
        cleanup_application = await create_application(
            env=lambda: {
                'APPLICATION_IP_WHITELIST__1': '1.2.3.4/32',
                'APPLICATION_IP_WHITELIST__2': '5.0.0.0/8',
                'X_FORWARDED_FOR_TRUSTED_HOPS': '2',
            }
        )
        self.add_async_cleanup(cleanup_application)

        await asyncio.sleep(6)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('Starting Test Application', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '6.5.4.3, 1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('Starting Test Application', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '5.1.1.1'},
        ) as response:
            content = await response.text()
        self.assertIn('Starting Test Application', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '6.5.4.3'},
        ) as response:
            content = await response.text()

        self.assertIn('Forbidden', content)
        self.assertEqual(response.status, 403)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/http',
            headers={'x-forwarded-for': '1.2.3.4, 6.5.4.3'},
        ) as response:
            content = await response.text()

        self.assertIn('Forbidden', content)
        self.assertEqual(response.status, 403)

        # The healthcheck is allowed from a private IP: simulates ALB
        async with session.request(
            'GET', 'http://localapps.com:8000/healthcheck'
        ) as response:
            content = await response.text()

        self.assertEqual('OK', content)
        self.assertEqual(response.status, 200)

        # ... and from a publically routable one: simulates Pingdom
        async with session.request(
            'GET',
            'http://localapps.com:8000/healthcheck',
            headers={'x-forwarded-for': '8.8.8.8'},
        ) as response:
            content = await response.text()

        self.assertEqual('OK', content)
        self.assertEqual(response.status, 200)

        # ... but not allowed to get to the application
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/healthcheck',
            headers={},
        ) as response:
            content = await response.text()

        # In production, hitting this URL without X-Forwarded-For should not
        # be possible, so a 500 is most appropriate
        self.assertEqual(response.status, 500)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.localapps.com:8000/healthcheck',
            headers={'x-forwarded-for': '8.8.8.8'},
        ) as response:
            content = await response.text()

        self.assertIn('Forbidden', content)
        self.assertEqual(response.status, 403)

    @async_test
    async def test_application_redirects_to_sso_again_if_token_expired(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        is_logged_in = True
        codes = iter(['some-code', 'some-other-code'])
        tokens = iter(['token-1', 'token-2'])
        auth_to_me = {
            # No token-1
            'Bearer token-2': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, number_of_times_at_sso = await create_sso(
            is_logged_in, codes, tokens, auth_to_me
        )
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        # Make a request to the home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertEqual(number_of_times_at_sso(), 2)
        self.assertEqual(200, response.status)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertIn('>Test Application</a>', content)

        self.assertIn('http://testapplication-23b40dd9.localapps.com:8000/', content)

    @async_test
    async def test_application_download(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        is_logged_in = True
        codes = iter(['some-code', 'some-other-code'])
        tokens = iter(['token-1', 'token-2'])
        auth_to_me = {
            # No token-1
            'Bearer token-2': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        stdout, stderr, code = await create_private_dataset()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://localapps.com:8000/catalogue/test_slug_g/test_slug_s'
        ) as response:
            content = await response.text()

        self.assertIn('You do not have permission to access these links', content)

        async with session.request(
            'GET', 'http://localapps.com:8000/table_data/my_database/public/auth_user'
        ) as response:
            content = await response.text()
            status = response.status

        self.assertEqual(status, 403)
        self.assertEqual(content, '')

        stdout, stderr, code = await give_user_dataset_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://localapps.com:8000/catalogue/test_slug_g/test_slug_s'
        ) as response:
            content = await response.text()

        self.assertNotIn('You do not have permission to access these links', content)

        async with session.request(
            'GET', 'http://localapps.com:8000/table_data/my_database/public/auth_user'
        ) as response:
            content = await response.text()

        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(
            rows[0],
            [
                'id',
                'password',
                'last_login',
                'is_superuser',
                'username',
                'first_name',
                'last_name',
                'email',
                'is_staff',
                'is_active',
                'date_joined',
            ],
        )
        self.assertEqual(rows[1][4], 'test@test.com')
        self.assertEqual(rows[2][0], 'Number of rows: 1')

    @async_test
    async def test_google_data_studio_download(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        is_logged_in = True
        codes = iter(['some-code', 'some-other-code'])
        tokens = iter(['token-1', 'token-2'])
        auth_to_me = {
            # No token-1
            'Bearer token-2': {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        # Check that with no token there is no access
        table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'
        stdout, stderr, code = await create_private_dataset()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'POST', f'http://localapps.com:8000/api/v1/table/{table_id}/schema'
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('Forbidden</h1>', content)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer something'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('Forbidden</h1>', content)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        async with session.request(
            'POST', f'http://localapps.com:8000/api/v1/table/{table_id}/rows'
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('Forbidden</h1>', content)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer something'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('Forbidden</h1>', content)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        stdout, stderr, code = await give_user_superuser_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure that superuser perms aren't enough...
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        stdout, stderr, code = await give_user_dataset_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure that superuser perms aren't enough...
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        # And that the table must be marked as GDS accessible
        stdout, stderr, code = await make_table_google_data_studio_accessible()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer token-2'},
            data=b'{"fields":[{"name":"id"}]}',
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(content)['schema'][0]['name'], 'id')
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(
                b'{"fields":[{"name":"id"},{"name":"password"},{"name":"last_login"},'
                b'{"name":"is_superuser"},{"name":"username"}]}'
            ),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json = json.loads(content)
        self.assertEqual(
            len(content_json['schema']), len(content_json['rows'][0]['values'])
        )
        self.assertEqual(content_json['schema'][0]['name'], 'id')
        self.assertEqual(content_json['schema'][1]['name'], 'password')
        self.assertEqual(content_json['schema'][2]['name'], 'last_login')
        self.assertEqual(content_json['schema'][3]['name'], 'is_superuser')
        self.assertEqual(content_json['schema'][4]['name'], 'username')
        self.assertEqual(content_json['rows'][0]['values'][2], None)
        self.assertEqual(content_json['rows'][0]['values'][3], True)
        self.assertEqual(content_json['rows'][0]['values'][4], 'test@test.com')

        # Test pagination
        stdout, stderr, code = await create_many_users()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(
                b'{"fields":[{"name":"username"}],"pagination":{"startRow":5.0,"rowCount":10.0}}'
            ),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json_1 = json.loads(content)
        self.assertEqual(len(content_json_1['rows']), 10)
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(
                b'{"fields":[{"name":"username"}],"pagination":{"startRow":3.0,"rowCount":5.0}}'
            ),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json_2 = json.loads(content)
        self.assertEqual(len(content_json_2['rows']), 5)
        self.assertEqual(content_json_1['rows'][0:2], content_json_2['rows'][2:4])

        # Check that even with a valid token, if a table doesn't exist, get a 403
        table_id_not_exists = '5f8117b4-e05d-442f-8622-8abab7141fd8'
        async with session.request(
            'POST',
            f'http://localapps.com:8000/api/v1/table/{table_id_not_exists}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual(content, '{}')


def client_session():
    session = aiohttp.ClientSession()

    async def _cleanup_session():
        await session.close()
        await asyncio.sleep(0.25)

    return session, _cleanup_session


async def create_sso(is_logged_in, codes, tokens, auth_to_me):
    number_of_times = 0
    latest_code = None

    async def handle_authorize(request):
        nonlocal number_of_times
        nonlocal latest_code

        number_of_times += 1

        if not is_logged_in:
            return web.Response(status=200, text='This is the login page')

        state = request.query['state']
        latest_code = next(codes)
        return web.Response(
            status=302,
            headers={
                'Location': request.query['redirect_uri']
                + f'?state={state}&code={latest_code}'
            },
        )

    async def handle_token(request):
        if (await request.post())['code'] != latest_code:
            return web.json_response({}, status=403)

        token = next(tokens)
        return web.json_response({'access_token': token}, status=200)

    async def handle_me(request):
        if request.headers['authorization'] in auth_to_me:
            return web.json_response(
                auth_to_me[request.headers['authorization']], status=200
            )

        return web.json_response({}, status=403)

    sso_app = web.Application()
    sso_app.add_routes(
        [
            web.get('/o/authorize/', handle_authorize),
            web.post('/o/token/', handle_token),
            web.get('/api/v1/user/me/', handle_me),
        ]
    )
    sso_runner = web.AppRunner(sso_app)
    await sso_runner.setup()
    sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8005)
    await sso_site.start()

    def get_number_of_times():
        return number_of_times

    return sso_runner.cleanup, get_number_of_times


# Run the application proper in a way that is as possible to production
# The environment must be the same as in the Dockerfile
async def create_application(env=lambda: {}):
    proc = await asyncio.create_subprocess_exec(
        '/dataworkspace/start.sh', env={**os.environ, **env()}, preexec_fn=os.setsid
    )

    async def _cleanup_application():
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)
        except ProcessLookupError:
            pass

    return _cleanup_application


async def flush_database():
    await (
        await asyncio.create_subprocess_shell(
            'django-admin flush --no-input --database default', env=os.environ
        )
    ).wait()


async def flush_redis():
    redis_client = await aioredis.create_redis('redis://data-workspace-redis:6379')
    await redis_client.execute('FLUSHDB')


async def give_user_superuser_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            User,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        user.is_superuser = True
        user.save()
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


async def give_user_app_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            Permission,
        )
        from django.contrib.auth.models import (
            User,
        )
        from django.contrib.contenttypes.models import (
            ContentType,
        )
        from dataworkspace.apps.applications.models import (
            ApplicationInstance,
        )
        permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        user.user_permissions.add(permission)
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


async def create_many_users():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            User,
        )
        for i in range(0, 200):
            User.objects.create(
                username='user_' + str(i) + '@example.com',
                email='user_' + str(i) + '@example.com',
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


async def create_private_dataset():
    python_code = textwrap.dedent(
        """\
        from dataworkspace.apps.core.models import Database
        from dataworkspace.apps.datasets.models import (
            DataGrouping,
            DataSet,
            SourceTable,
        )
        grouping = DataGrouping.objects.create(
            name="test_datagrouping",
            short_description="test_short_desc",
            slug="test_slug_g",
        )
        dataset = DataSet.objects.create(
            name="test_dataset",
            description="test_desc",
            short_description="test_short_desc",
            slug="test_slug_s",
            volume=1,
            grouping=grouping,
            published=True
        )
        SourceTable.objects.create(
            id="5a2ee5dd-f025-4939-b0a1-bb85ab7504d7",
            dataset=dataset,
            database=Database.objects.get(memorable_name="my_database"),
            schema="public",
            table="auth_user",
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


async def give_user_dataset_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.datasets.models import (
            DataSet,
            DataSetUserPermission,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        dataset = DataSet.objects.get(
            name="test_dataset",
        )
        DataSetUserPermission.objects.create(
            dataset=dataset,
            user=user,
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


async def make_table_google_data_studio_accessible():
    python_code = textwrap.dedent(
        """\
        from dataworkspace.apps.datasets.models import (
            SourceTable,
        )
        dataset = SourceTable.objects.get(
            id="5a2ee5dd-f025-4939-b0a1-bb85ab7504d7",
        )
        dataset.accessible_by_google_data_studio = True
        dataset.save()
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
