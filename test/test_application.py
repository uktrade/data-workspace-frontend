import asyncio
import csv
import io
import json
import os
import re
import signal
import textwrap
import unittest

import aiohttp
from aiohttp import web
import aiopg
import aioredis
import mohawk
from lxml import html

from dataworkspace.utils import DATA_EXPLORER_FLAG
from test.pages import HomePage, get_browser  # pylint: disable=wrong-import-order


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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        _, _, _ = await make_all_tools_visible()

        # Ensure the user doesn't see the application link since they don't
        # have permission
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()
        self.assertNotIn('Test Application', content)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Make a request to the tools page
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/tools/'
        ) as response:
            content = await response.text()

        # Ensure the user sees the link to the application
        self.assertEqual(200, response.status)
        self.assertIn('Test Application</button>', content)

        self.assertIn(
            'action="http://testapplication-23b40dd9.dataworkspace.test:8000/"', content
        )

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('Test Application is loading...', application_content_1)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        ) as response:
            application_content_2 = await response.text()

        self.assertIn('Test Application is loading...', application_content_2)

        await until_non_202(
            session, 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        )

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {'from-downstream': 'downstream-header-value'}

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
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
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
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
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/http'
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)

        async with session.request(
            'PATCH',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            data=b'1234',
        ) as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)
        self.assertEqual(received_content['content'], '1234')

        # Make a websockets connection to the proxy
        sent_headers = {'from-downstream-websockets': 'websockets-header-value'}
        async with session.ws_connect(
            'http://testapplication-23b40dd9.dataworkspace.test:8000/websockets',
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

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        ) as response:
            error_content = await response.text()

        self.assertIn('Application STOPPED', error_content)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('Test Application is loading...', content)

        await until_non_202(
            session, 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        )

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
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
    async def test_visualisation_shows_content_if_authorized_and_published(self):
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        stdout, stderr, code = await create_visualisation_echo('testvisualisation')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure the user doesn't see the visualisation link on the home page
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()
        self.assertNotIn('Test testvisualisation', content)

        # Ensure the user doesn't have access to the application
        async with session.request(
            'GET', 'http://testvisualisation.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # Ensure that the user can't see a visualisation which is published if they don't have authorization
        stdout, stderr, code = await toggle_visualisation_visibility(
            'testvisualisation', visible=True
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure the user doesn't have access to the application
        async with session.request(
            'GET', 'http://testvisualisation.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # Ensure that the user can't see a visualisation which is unpublished, even if if they have authorization
        stdout, stderr, code = await give_user_visualisation_perms('testvisualisation')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)
        stdout, stderr, code = await toggle_visualisation_visibility(
            'testvisualisation', visible=False
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure the user doesn't have access to the application
        async with session.request(
            'GET', 'http://testvisualisation.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # Finally, if the visualisation is published *and* they have authorization, they can see it.
        stdout, stderr, code = await toggle_visualisation_visibility(
            'testvisualisation', visible=True
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://testvisualisation.dataworkspace.test:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('testvisualisation is loading...', application_content_1)

        await until_non_202(
            session, 'http://testvisualisation.dataworkspace.test:8000/'
        )

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'GET',
            'http://testvisualisation.dataworkspace.test:8000/http',
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

        stdout, stderr, code = await set_visualisation_wrap(
            'testvisualisation', 'FULL_HEIGHT_IFRAME'
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET',
            'http://testvisualisation.dataworkspace.test:8000/',
            headers=sent_headers,
        ) as response:
            received_content = await response.text()

        self.assertIn(
            '<iframe src="http://testvisualisation--8888.dataworkspace.test:8000/"',
            received_content,
        )

        async with session.request(
            'GET',
            'http://testvisualisation--8888.dataworkspace.test:8000/http',
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
    async def test_visualisation_commit_shows_content_if_authorized(self):
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        stdout, stderr, code = await create_visualisation_echo('testvisualisation')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        def handle_users(request):
            return web.json_response([{'id': 1234}], status=200)

        project = {
            'id': 3,
            'name': 'testvisualisation',
            'tag_list': ['visualisation'],
            'default_branch': 'my-default-3',
            'description': 'The vis',
            'web_url': 'https://some.domain.test/',
        }

        def handle_project(request):
            return web.json_response(project)

        access_level = 20

        def handle_members(request):
            return web.json_response(
                [{'id': 1234, 'access_level': access_level}], status=200
            )

        def handle_general_gitlab(request):
            return web.json_response({})

        gitlab_cleanup = await create_server(
            8007,
            [
                web.get('/api/v4/users', handle_users),
                web.get('/api/v4/projects/3/members/all', handle_members),
                web.get('/api/v4/projects/3', handle_project),
                web.get('/{path:.*}', handle_general_gitlab),
            ],
        )
        self.add_async_cleanup(gitlab_cleanup)

        # Ensure the user doesn't have access to the application
        async with session.request(
            'GET', 'http://testvisualisation--11372717.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        access_level = 30

        async with session.request(
            'GET', 'http://testvisualisation--11372717.dataworkspace.test:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('testvisualisation [11372717]', application_content_1)
        self.assertIn('is loading...', application_content_1)

        await until_non_202(
            session, 'http://testvisualisation--11372717.dataworkspace.test:8000/'
        )

        sent_headers = {'from-downstream': 'downstream-header-value'}
        async with session.request(
            'GET',
            'http://testvisualisation--11372717.dataworkspace.test:8000/http',
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

        async with session.request(
            'GET',
            'http://testvisualisation--11372717--8888.dataworkspace.test:8000/http',
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
    async def test_visualisation_shows_dataset_if_authorised(self):
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Ensure user created
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            await response.text()

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

        dataset_id_dataset_1 = '0dea6147-d355-4b6d-a140-0304ef9cfeca'
        table_id = '39e3fa48-9352-471a-b278-3eca5ba92921'
        stdout, stderr, code = await create_private_dataset(
            'test_external_db',
            'MASTER',
            dataset_id_dataset_1,
            'dataset_1',
            table_id,
            'dataset_1',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        dataset_id_dataset_2 = 'ccddcf9a-4997-4761-bd5a-06854d0a6483'
        table_id = '426f6862-9880-4a1f-82a1-8496a5400820'
        stdout, stderr, code = await create_private_dataset(
            'test_external_db2',
            'MASTER',
            dataset_id_dataset_2,
            'dataset_2',
            table_id,
            'dataset_2',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        stdout, stderr, code = await create_visualisation_dataset(
            'testvisualisation-a', 3
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms(
            'testvisualisation-a'
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        def handle_users(request):
            return web.json_response([{'id': 1234}], status=200)

        def handle_project_3(request):
            return web.json_response(
                {
                    'id': 3,
                    'name': 'testvisualisation',
                    'tag_list': ['visualisation'],
                    'default_branch': 'master',
                    'description': 'The vis',
                    'web_url': 'https://some.domain.test/',
                }
            )

        def handle_project_4(request):
            return web.json_response(
                {
                    'id': 4,
                    'name': 'testvisualisation',
                    'tag_list': ['visualisation'],
                    'default_branch': 'master',
                    'description': 'The vis',
                    'web_url': 'https://some.domain.test/',
                }
            )

        def handle_members(request):
            return web.json_response([{'id': 1234, 'access_level': 30}], status=200)

        def handle_general_gitlab(request):
            return web.json_response({})

        gitlab_cleanup = await create_server(
            8007,
            [
                web.get('/api/v4/users', handle_users),
                web.get('/api/v4/projects/3/members/all', handle_members),
                web.get('/api/v4/projects/3', handle_project_3),
                web.get('/api/v4/projects/4/members/all', handle_members),
                web.get('/api/v4/projects/4', handle_project_4),
                web.get('/{path:.*}', handle_general_gitlab),
            ],
        )
        self.add_async_cleanup(gitlab_cleanup)

        stdout, stderr, code = await give_user_dataset_perms('dataset_1')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/datasets'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(403, status)

        await give_user_visualisation_developer_perms()

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/datasets'
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 200)
        csrf_token = re.match(
            r'.*name=\"csrfmiddlewaretoken\"\svalue=\"([^\"]+)\".*',
            content,
            flags=re.DOTALL,
        )[1]

        # The user only has access dataset_2, not dataset_1: we test that
        # a user cannot add access to a dataset they don't have access to
        async with session.request(
            'POST',
            'http://dataworkspace.test:8000/visualisations/3/datasets',
            data=(
                ('dataset', dataset_id_dataset_2),
                ('dataset', dataset_id_dataset_1),
                ('csrfmiddlewaretoken', csrf_token),
            ),
        ) as response:
            received_status = response.status
            await response.text()

        self.assertEqual(received_status, 200)

        async with session.request(
            'GET', 'http://testvisualisation-a.dataworkspace.test:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('testvisualisation-a is loading...', application_content_1)

        await until_non_202(
            session, 'http://testvisualisation-a.dataworkspace.test:8000/'
        )

        async with session.request(
            'GET',
            'http://testvisualisation-a.dataworkspace.test:8000/my_database/test_dataset',
        ) as response:
            received_status = response.status
            content = await response.text()

        # This application should not have permission to access the database,
        # and we get a simple 500 page from the visualisation in this case
        self.assertEqual(received_status, 500)
        self.assertEqual(
            content, '500 Internal Server Error\n\nServer got itself in trouble'
        )

        async with session.request(
            'GET',
            'http://testvisualisation-a.dataworkspace.test:8000/test_external_db2/dataset_2',
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 500)
        self.assertEqual(
            content, '500 Internal Server Error\n\nServer got itself in trouble'
        )

        async with session.request(
            'GET',
            'http://testvisualisation-a.dataworkspace.test:8000/test_external_db/dataset_1',
        ) as response:
            received_status = response.status
            content = await response.json()

        self.assertEqual(content, {'data': [1, 2]})

        # Stop the application
        async with session.request(
            'POST', 'http://testvisualisation-a.dataworkspace.test:8000/stop'
        ) as response:
            await response.text()

        # The first request after an application stopped unexpectedly should
        # be an error
        async with session.request(
            'GET', 'http://testvisualisation-a.dataworkspace.test:8000/'
        ) as response:
            content = await response.text()
        self.assertIn('Sorry, there is a problem with the service', content)

        # Give the visualisation permission to a dataset that the user
        # doesn't have access to.
        stdout, stderr, code = await give_visualisation_dataset_perms(
            'testvisualisation-a', 'dataset_2'
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/datasets'
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 200)
        csrf_token = re.match(
            r'.*name=\"csrfmiddlewaretoken\"\svalue=\"([^\"]+)\".*',
            content,
            flags=re.DOTALL,
        )[1]

        # No datasets posted, i.e. attempting to removing access from all datasets
        async with session.request(
            'POST',
            'http://dataworkspace.test:8000/visualisations/3/datasets',
            data=(('csrfmiddlewaretoken', csrf_token),),
        ) as response:
            received_status = response.status
            await response.text()

        async with session.request(
            'GET', 'http://testvisualisation-a.dataworkspace.test:8000/'
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('testvisualisation-a is loading...', application_content_1)

        await until_non_202(
            session, 'http://testvisualisation-a.dataworkspace.test:8000/'
        )

        # The application does have access to the dataset that the user does
        # not have access to, even though user tried to remove it
        async with session.request(
            'GET',
            'http://testvisualisation-a.dataworkspace.test:8000/test_external_db2/dataset_2',
        ) as response:
            received_status = response.status
            content = await response.json()

        self.assertEqual(content, {'data': [1, 2]})

        # The application now does not have access to the dataset that the
        # user removed
        async with session.request(
            'GET',
            'http://testvisualisation-a.dataworkspace.test:8000/test_external_db/dataset_1',
        ) as response:
            received_status = response.status
            content = await response.text()

        self.assertEqual(received_status, 500)
        self.assertEqual(
            content, '500 Internal Server Error\n\nServer got itself in trouble'
        )

        # Stop the application
        async with session.request(
            'POST', 'http://testvisualisation-a.dataworkspace.test:8000/stop'
        ) as response:
            await response.text()

        stdout, stderr, code = await create_visualisation_dataset(
            'testvisualisation-b', 4
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        stdout, stderr, code = await give_user_visualisation_perms(
            'testvisualisation-b'
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/4/datasets'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(200, status)
        self.assertNotIn('test_dataset', content)

        stdout, stderr, code = await give_visualisation_dataset_perms(
            'testvisualisation-b', 'test_dataset'
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/4/datasets'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertIn('test_dataset', content)

        async with session.request(
            'GET', 'http://testvisualisation-b.dataworkspace.test:8000/'
        ) as response:
            application_content_2 = await response.text()

        self.assertIn('testvisualisation-b is loading...', application_content_2)

        await until_non_202(
            session, 'http://testvisualisation-b.dataworkspace.test:8000/'
        )

        async with session.request(
            'GET',
            'http://testvisualisation-b.dataworkspace.test:8000/my_database/test_dataset',
        ) as response:
            received_status = response.status
            received_content = await response.json()

        self.assertEqual(received_content, {'data': list(range(1, 20001))})
        self.assertEqual(received_status, 200)

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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Make a request to the home page, which ensures the user is in the DB
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            await response.text()

        await asyncio.sleep(1)

        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/',
            params={'__memory_cpu': '1024_2048'},
        ) as response:
            application_content_1 = await response.text()

        self.assertIn('Test Application is loading...', application_content_1)

        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        ) as response:
            application_content_2 = await response.text()

        self.assertIn('Test Application is loading...', application_content_2)

        await until_non_202(
            session, 'http://testapplication-23b40dd9.dataworkspace.test:8000/'
        )

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {'from-downstream': 'downstream-header-value'}

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
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
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
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
            'http://testapplication-23b40dd9.dataworkspace.test:8000/websockets',
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

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Make a request to the application home page
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

        # Make a request to the application admin page
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/admin'
        ) as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

    @async_test
    async def test_application_shows_forbidden_if_not_auth_ip(self):
        await flush_database()
        await flush_redis()

        cleanup_sentry, sentry_requests = await create_sentry()
        self.add_async_cleanup(cleanup_sentry)

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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Make a request to the home page, which creates the user...
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            await response.text()

        # ... with application permissions...
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # ... and can make requests to the home page...
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()
        self.assertNotIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 200)

        # ... but not the application...
        async with session.request(
            'GET', 'http://testapplication-23b40dd9.dataworkspace.test:8000/http'
        ) as response:
            content = await response.text()
        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # ... and it can't be spoofed...
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        await cleanup_application()

        # ... but that X_FORWARDED_FOR_TRUSTED_HOPS and subnets are respected
        cleanup_application = await create_application(
            env=lambda: {
                'APPLICATION_IP_WHITELIST__1': '1.2.3.4/32',
                'APPLICATION_IP_WHITELIST__2': '5.0.0.0/8',
                'X_FORWARDED_FOR_TRUSTED_HOPS': '2',
                "SENTRY_DSN": "http://foobar@localhost:8009/123",
                "SENTRY_ENVIRONMENT": "Test",
            }
        )
        self.add_async_cleanup(cleanup_application)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Starting the application is asynchronous, with the proxy component starting up faster
        # than the Django application. So initial calls to the healthcheck fail at the proxy ->
        # Django phase, which cause the proxy to log exceptions to (the fake) Sentry. We wait for
        # these exceptions to make it to Sentry, and then clear our log of them so we can assert
        # on the ones deliberately sent later on in this test.
        await asyncio.sleep(1)
        sentry_requests.clear()

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('Test Application is loading...', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '6.5.4.3, 1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('Test Application is loading...', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '5.1.1.1'},
        ) as response:
            content = await response.text()
        self.assertIn('Test Application is loading...', content)
        self.assertEqual(response.status, 202)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '6.5.4.3'},
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/http',
            headers={'x-forwarded-for': '1.2.3.4, 6.5.4.3'},
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # The healthcheck is allowed from a private IP: simulates ALB
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/healthcheck'
        ) as response:
            content = await response.text()

        self.assertEqual('OK', content)
        self.assertEqual(response.status, 200)

        # ... and from a publically routable one: simulates Pingdom
        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/healthcheck',
            headers={'x-forwarded-for': '8.8.8.8'},
        ) as response:
            content = await response.text()

        self.assertEqual('OK', content)
        self.assertEqual(response.status, 200)

        # ... but not allowed to get to the application
        assert len(sentry_requests) == 0
        async with session.request(
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/healthcheck',
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
            'GET',
            'http://testapplication-23b40dd9.dataworkspace.test:8000/healthcheck',
            headers={'x-forwarded-for': '8.8.8.8'},
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

    @async_test
    async def test_integrated_data_explorer_has_ip_restrictions(self):
        await flush_database()
        await flush_redis()

        session, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        # Create application with a non-open whitelist
        cleanup_application = await create_application(
            env=lambda: {'APPLICATION_IP_WHITELIST__1': '1.2.3.4/32'}
        )
        self.add_async_cleanup(cleanup_application)

        await set_waffle_flag(DATA_EXPLORER_FLAG, everyone=True)

        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Make a request to the home page, which creates the user...
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            await response.text()

        # ... with application permissions...
        stdout, stderr, code = await give_user_app_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # ... and can make requests to the home page...
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            content = await response.text()
        self.assertNotIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 200)

        # ... but not data explorer...
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/data-explorer/'
        ) as response:
            content = await response.text()
        self.assertIn('You are not allowed to access this page', content)
        self.assertEqual(response.status, 403)

        # ... and it can't be spoofed...
        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/data-explorer/',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('You are not allowed to access this page', content)
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

        await set_waffle_flag(DATA_EXPLORER_FLAG, everyone=True)
        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/data-explorer/',
            headers={'x-forwarded-for': '1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('This is a page.', content)
        self.assertEqual(response.status, 200)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/data-explorer/',
            headers={'x-forwarded-for': '6.5.4.3, 1.2.3.4'},
        ) as response:
            content = await response.text()
        self.assertIn('This is a page.', content)
        self.assertEqual(response.status, 200)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/data-explorer/',
            headers={'x-forwarded-for': '5.1.1.1'},
        ) as response:
            content = await response.text()
        self.assertIn('This is a page.', content)
        self.assertEqual(response.status, 200)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/data-explorer/',
            headers={'x-forwarded-for': '6.5.4.3'},
        ) as response:
            content = await response.text()

        self.assertIn('You are not allowed to access this page', content)
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, number_of_times_at_sso = await create_sso(
            is_logged_in, codes, tokens, auth_to_me
        )
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Make a request to the home page
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/'
        ) as response:
            self.assertEqual(number_of_times_at_sso(), 2)
            self.assertEqual(200, response.status)

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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        dataset_id_test_dataset = '70ce6fdd-1791-4806-bbe0-4cf880a9cc37'
        table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'

        stdout, stderr, code = await create_metadata_table()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        stdout, stderr, code = await create_private_dataset(
            'my_database',
            'DATACUT',
            dataset_id_test_dataset,
            'test_dataset',
            table_id,
            'test_dataset',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET', f'http://dataworkspace.test:8000/datasets/{dataset_id_test_dataset}'
        ) as response:
            content = await response.text()

        self.assertIn('You do not have permission to access these links', content)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/table_data/my_database/public/test_dataset',
        ) as response:
            content = await response.text()
            status = response.status

        self.assertEqual(status, 403)
        self.assertEqual(content, '')

        stdout, stderr, code = await give_user_dataset_perms('test_dataset')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/datasets/70ce6fdd-1791-4806-bbe0-4cf880a9cc37',
        ) as response:
            content = await response.text()

        self.assertNotIn('You do not have permission to access these links', content)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/table_data/my_database/public/test_dataset',
        ) as response:
            content = await response.text()

        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(rows[0], ['id', 'data'])
        self.assertEqual(rows[1][1], 'test data 1')
        self.assertEqual(rows[2][1], 'test data 2')
        self.assertEqual(rows[20001][0], 'Number of rows: 20000')

        async def fetch_num_connections():
            pool = await aiopg.create_pool(
                'dbname=dataworkspace user=postgres password=postgres '
                'host=data-workspace-postgres'
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
            'GET',
            'http://dataworkspace.test:8000/table_data/my_database/public/test_dataset',
        )
        num_connections_2 = await fetch_num_connections()
        response_2 = await session.request(
            'GET',
            'http://dataworkspace.test:8000/table_data/my_database/public/test_dataset',
        )
        num_connections_3 = await fetch_num_connections()
        response_3 = await session.request(
            'GET',
            'http://dataworkspace.test:8000/table_data/my_database/public/test_dataset',
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

        self.assertEqual(rows_1[20001][0], 'Number of rows: 20000')
        self.assertEqual(rows_2[20001][0], 'Number of rows: 20000')
        self.assertEqual(rows_3[20001][0], 'Number of rows: 20000')

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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Check that with no token there is no access
        dataset_id = '70ce6fdd-1791-4806-bbe0-4cf880a9cc37'
        table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'
        stdout, stderr, code = await create_private_dataset(
            'my_database',
            'MASTER',
            dataset_id,
            'test_dataset',
            table_id,
            'test_dataset',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request(
            'POST', f'http://dataworkspace.test:8000/api/v1/table/{table_id}/schema'
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('You are not allowed to access this page</h1>', content)
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer something'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('You are not allowed to access this page</h1>', content)
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        async with session.request(
            'POST', f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows'
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('You are not allowed to access this page</h1>', content)
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer something'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertIn('You are not allowed to access this page</h1>', content)
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
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
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual('{}', content)

        stdout, stderr, code = await give_user_dataset_perms('test_dataset')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        # Ensure that superuser perms aren't enough...
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
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
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/schema',
            headers={'Authorization': 'Bearer token-2'},
            data=b'{"fields":[{"name":"data"}]}',
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(content)['schema'][0]['name'], 'id')
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=b'{"fields":[{"name":"data"}]}',
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json = json.loads(content)
        self.assertEqual(
            len(content_json['schema']), len(content_json['rows'][0]['values'])
        )
        self.assertEqual(content_json['schema'][0]['name'], 'data')
        self.assertEqual(content_json['rows'][0]['values'][0], 'test data 1')
        self.assertEqual(content_json['rows'][1]['values'][0], 'test data 2')
        self.assertEqual(len(content_json['rows']), 20000)

        # Test pagination
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(
                b'{"fields":[{"name":"data"}],"pagination":{"startRow":1.0,"rowCount":10.0}}'
            ),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json_1 = json.loads(content)
        self.assertEqual(len(content_json_1['rows']), 10)
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(
                b'{"fields":[{"name":"data"}],"pagination":{"startRow":2.0,"rowCount":5.0}}'
            ),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json_2 = json.loads(content)
        self.assertEqual(len(content_json_2['rows']), 5)
        self.assertEqual(content_json_1['rows'][1:2], content_json_2['rows'][0:1])

        # Test $searchAfter
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id}/rows',
            headers={'Authorization': 'Bearer token-2'},
            data=(b'{"fields":[{"name":"data"}],"$searchAfter":[1]}'),
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        content_json_1 = json.loads(content)
        self.assertEqual(content_json_1['rows'][0]['values'][0], 'test data 2')

        # Check that even with a valid token, if a table doesn't exist, get a 403
        table_id_not_exists = '5f8117b4-e05d-442f-8622-8abab7141fd8'
        async with session.request(
            'POST',
            f'http://dataworkspace.test:8000/api/v1/table/{table_id_not_exists}/rows',
            headers={'Authorization': 'Bearer token-2'},
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 403)
        self.assertEqual(content, '{}')

    @async_test
    async def test_hawk_authenticated_source_table_api_endpoint(self):
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        # Check that with no authorization header there is no access
        dataset_id = '70ce6fdd-1791-4806-bbe0-4cf880a9cc37'
        table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'
        url = f'http://dataworkspace.test:8000/api/v1/dataset/{dataset_id}/{table_id}'
        stdout, stderr, code = await create_private_dataset(
            'my_database',
            'MASTER',
            dataset_id,
            'test_dataset',
            table_id,
            'test_dataset',
        )
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request('GET', url) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

        # unauthenticated request
        client_id = os.environ['HAWK_SENDERS__1__id']
        client_key = 'incorrect_key'
        algorithm = os.environ['HAWK_SENDERS__1__algorithm']
        method = 'GET'
        content = ''
        content_type = ''
        credentials = {'id': client_id, 'key': client_key, 'algorithm': algorithm}
        sender = mohawk.Sender(
            credentials=credentials,
            url=url,
            method=method,
            content=content,
            content_type=content_type,
        )
        headers = {'Authorization': sender.request_header, 'Content-Type': content_type}

        async with session.request('GET', url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

        # authenticated request
        client_id = os.environ['HAWK_SENDERS__1__id']
        client_key = os.environ['HAWK_SENDERS__1__key']
        algorithm = os.environ['HAWK_SENDERS__1__algorithm']
        method = 'GET'
        content = ''
        content_type = ''
        credentials = {'id': client_id, 'key': client_key, 'algorithm': algorithm}
        sender = mohawk.Sender(
            credentials=credentials,
            url=url,
            method=method,
            content=content,
            content_type=content_type,
        )
        headers = {'Authorization': sender.request_header, 'Content-Type': content_type}

        async with session.request('GET', url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)

        # replay attack
        async with session.request('GET', url, headers=headers) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 401)

    @async_test
    async def test_mirror(self):
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
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        mirror_cleanup = await create_mirror()
        self.add_async_cleanup(mirror_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        async with session.request(
            'GET',
            'http://testvisualisation--11372717.dataworkspace.test:8000/__mirror/some/path/in/mirror',
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)
        self.assertEqual(
            content, 'Mirror path: /some-remote-folder/some/path/in/mirror'
        )

    @async_test
    async def test_gitlab_application_can_be_managed(self):
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
            'Bearer token-2': {
                'email': 'test@test.com',
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations'
        ) as response:
            status = response.status
        self.assertEqual(status, 403)

        await give_user_visualisation_developer_perms()

        def handle_group(request):
            return web.json_response(
                {'web_url': 'https://some.domain.test/'}, status=200
            )

        users_query = {}

        def handle_users(request):
            nonlocal users_query
            users_query = request.query
            return web.json_response([{'id': 1234}], status=200)

        project = {
            'id': 3,
            'name': 'Michal\'s Vis_ualisat-tion---',
            'tag_list': ['visualisation'],
            'default_branch': 'my-default-3',
            'description': 'The vis',
            'web_url': 'https://some.domain.test/',
        }
        projects_query = {}

        def handle_projects(request):
            nonlocal projects_query
            projects_query = request.query
            return web.json_response(
                [
                    {
                        'id': 1,
                        'name': 'not-a-vis',
                        'tag_list': ['some-tag'],
                        'default_branch': 'my-default-1',
                    },
                    {
                        'id': 2,
                        'name': 'is-a-vis',
                        'tag_list': ['visualisation'],
                        'default_branch': 'my-default-2',
                    },
                    project,
                ],
                status=200,
            )

        def handle_project(request):
            return web.json_response(project)

        access_level = 30

        def handle_members(request):
            return web.json_response(
                [{'id': 1234, 'access_level': access_level}], status=200
            )

        def handle_branches(request):
            return web.json_response(
                [
                    {
                        'name': 'my-default-3',
                        'commit': {
                            'id': 'some-id',
                            'short_id': 'abcdef12',
                            'committed_date': '2015-01-01T01:01:01.000Z',
                        },
                    },
                    {
                        'name': 'feature/my-feature-3',
                        'commit': {
                            'id': 'some-id',
                            'short_id': 'abcdef12',
                            'committed_date': '2015-01-01T01:01:01.000Z',
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
                web.get('/api/v4/groups/visualisations', handle_group),
                web.get('/api/v4/users', handle_users),
                web.get('/api/v4/projects', handle_projects),
                web.get('/api/v4/projects/3/members/all', handle_members),
                web.get('/api/v4/projects/3', handle_project),
                web.get('/api/v4/projects/3/repository/branches', handle_branches),
                web.get('/{path:.*}', handle_general_gitlab),
            ],
        )
        self.add_async_cleanup(gitlab_cleanup)

        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations'
        ) as response:
            status = response.status
            content = await response.text()
        self.assertEqual(status, 200)

        self.assertEqual(
            users_query['extern_uid'], '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2'
        )
        self.assertEqual(projects_query['sudo'], '1234')
        self.assertNotIn('not-a-vis', content)
        self.assertIn('is-a-vis', content)

        access_level = 20
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/users/give-access'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 403)
        self.assertNotIn('Give access', content)

        access_level = 30
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/users/give-access'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn('Give access', content)

        def handle_general_ecr(request):
            return web.json_response(
                {
                    'imageDetails': [
                        {'imageTags': ['michals-vis-ualisat-tion--abcdef12']}
                    ]
                }
            )

        ecr_cleanup = await create_server(
            8008, [web.post('/{path:.*}', handle_general_ecr)]
        )
        self.add_async_cleanup(ecr_cleanup)

        async with session.request(
            'GET',
            'http://dataworkspace.test:8000/visualisations/3/branches/my-default-3',
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn('Production: abcdef12', content)

        self.assertIn(
            'href="http://michals-vis-ualisat-tion.dataworkspace.test:8000/', content
        )
        self.assertIn(
            'href="http://michals-vis-ualisat-tion--abcdef12.dataworkspace.test:8000/',
            content,
        )

        # Check that the access level must have been cached
        access_level = 20
        async with session.request(
            'GET', 'http://dataworkspace.test:8000/visualisations/3/users/give-access'
        ) as response:
            status = response.status
            content = await response.text()

        self.assertEqual(status, 200)
        self.assertIn('Give access', content)

    @async_test
    async def test_sentry_dsn_does_not_stop_proxy_from_becoming_healthy(self):
        _, cleanup_session = client_session()
        self.add_async_cleanup(cleanup_session)

        cleanup_sentry, _ = await create_sentry()
        self.add_async_cleanup(cleanup_sentry)

        cleanup_application = await create_application(
            env=lambda: {
                "SENTRY_DSN": "http://foobar@localhost:8009/123",
                "SENTRY_ENVIRONMENT": "Test",
            }
        )
        self.add_async_cleanup(cleanup_application)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

    @async_test
    async def test_search_filter_result_predictions(self):
        cleanup_application = await create_application()
        self.add_async_cleanup(cleanup_application)

        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await until_succeeds('http://dataworkspace.test:8000/healthcheck')

        _, _, code = await create_sample_datasets_and_visualisations()
        assert code == 0

        browser = await get_browser()
        home_page = await HomePage(browser=browser).open()

        with_no_filters = find_search_filter_labels(await home_page.get_html())
        assert "You have access (4)" in with_no_filters
        assert "Download (1)" in with_no_filters
        assert "Analyse in tools (2)" in with_no_filters
        assert "Use as reference data (1)" in with_no_filters
        assert "View data visualisation (1)" in with_no_filters
        assert "DIT (1)" in with_no_filters
        assert "ONS (1)" in with_no_filters
        assert "HMRC (1)" in with_no_filters

        # Toggle the master dataset filter on (filters: master)
        await home_page.toggle_filter("Analyse in tools")

        with_master_filter = find_search_filter_labels(await home_page.get_html())
        assert "You have access (1)" in with_master_filter
        assert "Download (1)" in with_master_filter
        assert "Analyse in tools (2)" in with_master_filter
        assert "Use as reference data (1)" in with_master_filter
        assert "View data visualisation (1)" in with_master_filter
        assert "DIT (1)" in with_master_filter
        assert not any(f.startswith("ONS") for f in with_master_filter)
        assert "HMRC (1)" in with_master_filter

        # Toggle the reference dataset filter on (filters: master, reference)
        await home_page.toggle_filter("Use as reference data")

        with_master_and_reference_filters = find_search_filter_labels(
            await home_page.get_html()
        )
        assert "You have access (2)" in with_master_and_reference_filters
        assert "Download (1)" in with_master_and_reference_filters
        assert "Analyse in tools (2)" in with_master_and_reference_filters
        assert "Use as reference data (1)" in with_master_and_reference_filters
        assert "View data visualisation (1)" in with_master_and_reference_filters
        assert "DIT (1)" in with_master_and_reference_filters
        assert not any(f.startswith("ONS") for f in with_master_and_reference_filters)
        assert "HMRC (1)" in with_master_and_reference_filters

        # Toggle the master dataset filter back off (filters: reference)
        await home_page.toggle_filter("Analyse in tools")

        with_reference_filter = find_search_filter_labels(await home_page.get_html())
        assert "You have access (1)" in with_reference_filter
        assert "Download (1)" in with_reference_filter
        assert "Analyse in tools (2)" in with_reference_filter
        assert "Use as reference data (1)" in with_reference_filter
        assert "View data visualisation (1)" in with_reference_filter
        assert not any(f.startswith("DIT") for f in with_reference_filter)
        assert not any(f.startswith("ONS") for f in with_reference_filter)
        assert not any(f.startswith("HMRC") for f in with_reference_filter)

        # Toggle the authorization filter on (filters: authorization, reference)
        await home_page.toggle_filter("You have access")

        with_authorization_and_reference_filters = find_search_filter_labels(
            await home_page.get_html()
        )
        assert "You have access (1)" in with_authorization_and_reference_filters
        assert "Download (1)" in with_authorization_and_reference_filters
        assert "Analyse in tools (1)" in with_authorization_and_reference_filters
        assert "Use as reference data (1)" in with_authorization_and_reference_filters
        assert "View data visualisation (1)" in with_authorization_and_reference_filters
        assert not any(
            f.startswith("DIT") for f in with_authorization_and_reference_filters
        )
        assert not any(
            f.startswith("ONS") for f in with_authorization_and_reference_filters
        )
        assert not any(
            f.startswith("HMRC") for f in with_authorization_and_reference_filters
        )

        # Toggle the authorization filter off, reference filter off, and the "DIT" source tag on (filters: DIT)
        await home_page.toggle_filter("You have access")
        await home_page.toggle_filter("Use as reference data")
        await home_page.toggle_filter("DIT")

        with_dit_filter = find_search_filter_labels(await home_page.get_html())
        assert "You have access (1)" in with_dit_filter
        assert "Download (0)" in with_dit_filter
        assert "Analyse in tools (1)" in with_dit_filter
        assert "Use as reference data (0)" in with_dit_filter
        assert "View data visualisation (0)" in with_dit_filter
        assert "DIT (1)" in with_dit_filter
        assert "ONS (1)" in with_dit_filter
        assert "HMRC (1)" in with_dit_filter

        # Toggle the "ONS" source tag on (filters: DIT, ONS)
        await home_page.toggle_filter("ONS")

        with_dit_and_ons_filters = find_search_filter_labels(await home_page.get_html())
        assert "You have access (2)" in with_dit_and_ons_filters
        assert "Download (1)" in with_dit_and_ons_filters
        assert "Analyse in tools (1)" in with_dit_and_ons_filters
        assert "Use as reference data (0)" in with_dit_and_ons_filters
        assert "View data visualisation (0)" in with_dit_and_ons_filters
        assert "DIT (1)" in with_dit_and_ons_filters
        assert "ONS (1)" in with_dit_and_ons_filters
        assert "HMRC (1)" in with_dit_and_ons_filters


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


async def create_server(port, routes):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    return runner.cleanup


async def create_mirror():
    async def handle(request):
        return web.Response(text=f'Mirror path: {request.path}', status=200)

    mirror_app = web.Application()
    mirror_app.add_routes([web.get('/{path:.*}', handle)])
    mirror_runner = web.AppRunner(mirror_app)
    await mirror_runner.setup()
    mirror_site = web.TCPSite(mirror_runner, '0.0.0.0', 8006)
    await mirror_site.start()

    return mirror_runner.cleanup


async def create_sentry():
    sentry_requests = []

    async def handle(request):
        nonlocal sentry_requests
        sentry_requests.append(request)
        return web.Response(text='OK', status=200)

    sentry_app = web.Application()
    sentry_app.add_routes([web.post('/{path:.*}', handle)])
    sentry_runner = web.AppRunner(sentry_app)
    await sentry_runner.setup()
    sentry_site = web.TCPSite(sentry_runner, '0.0.0.0', 8009)
    await sentry_site.start()

    return sentry_runner.cleanup, sentry_requests


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


async def make_all_tools_visible():
    python_code = textwrap.dedent(
        """\
        from dataworkspace.apps.applications.models import (
            ApplicationTemplate,
        )
        ApplicationTemplate.objects.all().update(visible=True)
        """
    ).encode('ascii')
    make_visible = await asyncio.create_subprocess_shell(
        'django-admin shell',
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await make_visible.communicate(python_code)
    code = await make_visible.wait()

    return stdout, stderr, code


async def until_succeeds(url):
    loop = asyncio.get_running_loop()
    fail_if_later = loop.time() + 120
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(connect=1.0)
    ) as session:
        while True:
            try:
                async with session.request('GET', url) as response:
                    response.raise_for_status()
            except (aiohttp.ClientConnectorError, aiohttp.ClientResponseError):
                if loop.time() >= fail_if_later:
                    raise
                await asyncio.sleep(0.1)
            else:
                break


async def until_non_202(session, url):
    for _ in range(0, 600):
        async with session.request('GET', url) as response:
            if response.status != 202:
                return
        await asyncio.sleep(0.1)

    raise Exception()


async def flush_database():
    await (  # noqa
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


async def give_user_visualisation_developer_perms():
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
            codename='develop_visualisations',
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


async def create_metadata_table():
    python_code = textwrap.dedent(
        """\
        from django.db import connections
        with connections["my_database"].cursor() as cursor:
            cursor.execute(
                '''
                CREATE SCHEMA IF NOT EXISTS dataflow;
                CREATE TABLE IF NOT EXISTS dataflow.metadata (
                    id int, table_schema text, table_name text, source_data_modified_utc timestamp
                );
                '''
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


async def create_private_dataset(
    database, dataset_type, dataset_id, dataset_name, table_id, table_name
):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.core.models import Database
        from dataworkspace.apps.datasets.models import (
            DataSet,
            SourceTable,
            DatasetReferenceCode,
        )
        from dataworkspace.apps.datasets.constants import DataSetType
        reference_code, _ = DatasetReferenceCode.objects.get_or_create(code='TEST')
        dataset = DataSet.objects.create(
            name="{dataset_name}",
            description="test_desc",
            short_description="test_short_desc",
            slug="{dataset_name}",
            id="{dataset_id}",
            published=True,
            reference_code=reference_code,
            type=DataSetType.{dataset_type}.value,
        )
        SourceTable.objects.create(
            id="{table_id}",
            dataset=dataset,
            database=Database.objects.get(memorable_name="{database}"),
            schema="public",
            table="{table_name}",
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


async def give_user_dataset_perms(name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.datasets.models import (
            DataSet,
            DataSetUserPermission,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        dataset = DataSet.objects.get(
            name="{name}",
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


async def give_user_visualisation_perms(name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.applications.models import VisualisationTemplate
        from dataworkspace.apps.datasets.models import VisualisationUserPermission, VisualisationCatalogueItem
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        visualisationtemplate = VisualisationTemplate.objects.get(
            host_basename="{name}",
        )
        VisualisationUserPermission.objects.create(
            user=user,
            visualisation=VisualisationCatalogueItem.objects.get(visualisation_template=visualisationtemplate),
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


async def create_visualisation_echo(name):
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
            spawner_options='{{"CMD":["python3", "/test/echo_server.py"]}}',
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


async def toggle_visualisation_visibility(name, visible=True):
    python_code = textwrap.dedent(
        f"""\
from dataworkspace.apps.applications.models import (
    VisualisationTemplate,
)
template = VisualisationTemplate.objects.get(
    host_basename="{name}"
)
template.visible = {visible}
template.save()
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


async def set_visualisation_wrap(name, wrap):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import (
            VisualisationTemplate,
        )
        template = VisualisationTemplate.objects.get(
            host_basename="{name}"
        )
        template.wrap = "{wrap}"
        template.save()
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


async def create_visualisation_dataset(name, gitlab_project_id):
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
            spawner_options='{{"CMD":["python3", "/test/dataset_server.py"]}}',
            spawner_time=60,
            gitlab_project_id={gitlab_project_id},
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


async def give_visualisation_dataset_perms(vis_name, dataset_name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.applications.models import (
            ApplicationTemplate,
        )
        from dataworkspace.apps.datasets.models import (
            DataSet,
            DataSetApplicationTemplatePermission,
        )
        application_template = ApplicationTemplate.objects.get(host_basename="{vis_name}")
        dataset = DataSet.objects.get(
            name="{dataset_name}",
        )
        DataSetApplicationTemplatePermission.objects.create(
            application_template=application_template,
            dataset=dataset,
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


async def set_waffle_flag(flag_name, everyone=True):
    python_code = textwrap.dedent(
        f"""
        from waffle.models import Flag

        flag = Flag.objects.create(name='{flag_name}', everyone={everyone})
        flag.save()
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


async def create_sample_datasets_and_visualisations():
    """Creates one of each type of dataset/visualisation

    WARNING: removes any pre-existing datasets/visualisations

    Creates 5 datasets/visualisations:
    1) Master dataset, available to all, with DIT source tag
    2) Master dataset, restricted access (with no grants), with HMRC source tag
    3) Datacut, available to all, with ONS source tag
    4) Reference data, available to all
    5) Visualisation, available to all.
    """
    python_code = textwrap.dedent(
        """
import random

from django.db import IntegrityError
import factory

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import SourceTag
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.models import ReferenceDataset
from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
from dataworkspace.tests import factories


DataSet.objects.all().delete()
ReferenceDataset.objects.all().delete()
VisualisationCatalogueItem.objects.all().delete()

for dept in ('DIT', 'HMRC', 'ONS'):
    SourceTag.objects.get_or_create(name=dept)

source_tags = {st.name: st for st in SourceTag.objects.all()}

def paragraph(_):
    from faker import Faker
    return Faker().paragraph(5)

try:
    master = factories.DataSetFactory(
        id=1,
        name="Master 1",
        slug="master-1",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.MASTER.value,
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    master = DataSet.objects.get(id=1)

master.source_tags.set([source_tags['DIT']])

try:
    master = factories.DataSetFactory(
        id=2,
        name="Master 2",
        slug="master-2",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.MASTER.value,
        published=True,
        user_access_type='REQUIRES_AUTHORIZATION',
    )
except IntegrityError:
    master = DataSet.objects.get(id=2)

master.source_tags.set([source_tags['HMRC']])

try:
    datacut = factories.DataSetFactory(
        id=3,
        name="Datacut 1",
        slug="datacut-1",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.DATACUT.value,
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    datacut = DataSet.objects.get(id=3)

datacut.source_tags.set([source_tags['ONS']])

try:
    factories.ReferenceDatasetFactory(
        id=1,
        name=f"Reference 1",
        slug=f"reference-1",
        description=factory.LazyAttribute(paragraph),
        published=True,
    )
except IntegrityError:
    pass

try:
    factories.VisualisationCatalogueItemFactory(
        id=1,
        name="Visualisation 1",
        description=factory.LazyAttribute(paragraph),
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    pass
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


def find_search_filter_labels(html_):
    doc = html.fromstring(html_)
    return {
        label.strip()
        for label in doc.xpath('//div[@id="live-search-wrapper"]//label/text()')
    }
