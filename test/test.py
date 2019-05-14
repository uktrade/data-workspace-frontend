import asyncio
import json
import os
import unittest
from unittest.mock import (
    patch,
)

import aiohttp
from aiohttp import web

from app.proxy import async_main


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
        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            proc.terminate()
            await asyncio.sleep(2)
        proc = await asyncio.create_subprocess_exec(
            '/app/start.sh',
            env={
                # Static: as in Dockerfile
                'PYTHONPATH': '/app',
                'DJANGO_SETTINGS_MODULE': 'app.settings',
                # Dynamic: proxy and app settings populated at runtime
                'AUTHBROKER_CLIENT_ID': 'some-id',
                'AUTHBROKER_CLIENT_SECRET': 'some-secret',
                'AUTHBROKER_URL': 'http://localhost:8005/',
                'REDIS_URL': 'redis://analysis-workspace-redis:6379',
                'SECRET_KEY': 'localhost',
                'ALLOWED_HOSTS__1': 'localhost',
                'ADMIN_DB__NAME': 'postgres',
                'ADMIN_DB__USER': 'postgres',
                'ADMIN_DB__PASSWORD': 'postgres',
                'ADMIN_DB__HOST': 'jupyteradminpostgres',
                'ADMIN_DB__PORT': '5432',
                'DATA_DB__my_database__NAME': 'postgres',
                'DATA_DB__my_database__USER': 'postgres',
                'DATA_DB__my_database__PASSWORD': 'postgres',
                'DATA_DB__my_database__HOST': 'jupyteradminpostgres',
                'DATA_DB__my_database__PORT': '5432',
                'APPSTREAM_URL': 'https://url.to.appstream',
                'SUPPORT_URL': 'https://url.to.support/',
                'NOTEBOOKS_URL': 'https://url.to.notebooks/',
                'OAUTHLIB_INSECURE_TRANSPORT': '1',
            },
        )
        self.add_async_cleanup(cleanup_application)

        # Start a mock SSO
        async def handle_authorize(request):
            # The user would login here, and eventually redirect back to redirect_uri
            state = request.query['state']
            code = 'some-code'
            return web.Response(status=302, headers={
                'Location': request.query['redirect_uri'] + f'?state={state}&code={code}',
            })

        token_request_code = None
        async def handle_token(request):
            nonlocal token_request_code
            token_request_code = (await request.post())['code']
            return web.json_response({'access_token': 'some-token'}, status=200)

        me_request_auth = None
        async def handle_me(request):
            nonlocal me_request_auth
            me_request_auth = request.headers['Authorization']
            data = {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
            return web.json_response(data, status=200, headers={
            })
        sso_app = web.Application()
        sso_app.add_routes([
            web.get('/o/authorize/', handle_authorize),
            web.post('/o/token/', handle_token),
            web.get('/api/v1/user/me/', handle_me),
        ])
        sso_runner = web.AppRunner(sso_app)
        await sso_runner.setup()
        self.add_async_cleanup(sso_runner.cleanup)
        sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8005)
        await sso_site.start()

        await asyncio.sleep(2)

        session = aiohttp.ClientSession()
        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Make a request to the home page
        async with session.request('GET', 'http://localhost:8000/') as response:
            content = await response.text()

        # Ensure we sent the right thing to SSO
        self.assertEqual('some-code', token_request_code)
        self.assertEqual('Bearer some-token', me_request_auth)

        # Ensure the user sees the content from the application
        self.assertEqual(200, response.status)
        self.assertIn('JupyterLab', content)

    @async_test
    async def test_application_redirects_to_sso_if_initially_not_authorized(self):
        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            proc.terminate()
            await asyncio.sleep(2)
        proc = await asyncio.create_subprocess_exec(
            '/app/start.sh',
            env={
                # Static: as in Dockerfile
                'PYTHONPATH': '/app',
                'DJANGO_SETTINGS_MODULE': 'app.settings',
                # Dynamic: proxy and app settings populated at runtime
                'AUTHBROKER_CLIENT_ID': 'some-id',
                'AUTHBROKER_CLIENT_SECRET': 'some-secret',
                'AUTHBROKER_URL': 'http://localhost:8005/',
                'REDIS_URL': 'redis://analysis-workspace-redis:6379',
                'SECRET_KEY': 'localhost',
                'ALLOWED_HOSTS__1': 'localhost',
                'ADMIN_DB__NAME': 'postgres',
                'ADMIN_DB__USER': 'postgres',
                'ADMIN_DB__PASSWORD': 'postgres',
                'ADMIN_DB__HOST': 'jupyteradminpostgres',
                'ADMIN_DB__PORT': '5432',
                'DATA_DB__my_database__NAME': 'postgres',
                'DATA_DB__my_database__USER': 'postgres',
                'DATA_DB__my_database__PASSWORD': 'postgres',
                'DATA_DB__my_database__HOST': 'jupyteradminpostgres',
                'DATA_DB__my_database__PORT': '5432',
                'APPSTREAM_URL': 'https://url.to.appstream',
                'SUPPORT_URL': 'https://url.to.support/',
                'NOTEBOOKS_URL': 'https://url.to.notebooks/',
                'OAUTHLIB_INSECURE_TRANSPORT': '1',
            },
        )
        self.add_async_cleanup(cleanup_application)

        # Start a limited mock SSO
        async def handle_authorize(request):
            return web.Response(status=200, text='This is the login page')

        sso_app = web.Application()
        sso_app.add_routes([
            web.get('/o/authorize/', handle_authorize),
        ])
        sso_runner = web.AppRunner(sso_app)
        await sso_runner.setup()
        self.add_async_cleanup(sso_runner.cleanup)
        sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8005)
        await sso_site.start()

        await asyncio.sleep(2)

        session = aiohttp.ClientSession()
        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Make a request to the application home page
        async with session.request('GET', 'http://localhost:8000/') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

        # Make a request to the application admin page
        async with session.request('GET', 'http://localhost:8000/admin') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

    @async_test
    async def test_application_redirects_to_sso_again_if_token_expired(self):
        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            proc.terminate()
            await asyncio.sleep(2)
        proc = await asyncio.create_subprocess_exec(
            '/app/start.sh',
            env={
                # Static: as in Dockerfile
                'PYTHONPATH': '/app',
                'DJANGO_SETTINGS_MODULE': 'app.settings',
                # Dynamic: proxy and app settings populated at runtime
                'AUTHBROKER_CLIENT_ID': 'some-id',
                'AUTHBROKER_CLIENT_SECRET': 'some-secret',
                'AUTHBROKER_URL': 'http://localhost:8005/',
                'REDIS_URL': 'redis://analysis-workspace-redis:6379',
                'SECRET_KEY': 'localhost',
                'ALLOWED_HOSTS__1': 'localhost',
                'ADMIN_DB__NAME': 'postgres',
                'ADMIN_DB__USER': 'postgres',
                'ADMIN_DB__PASSWORD': 'postgres',
                'ADMIN_DB__HOST': 'jupyteradminpostgres',
                'ADMIN_DB__PORT': '5432',
                'DATA_DB__my_database__NAME': 'postgres',
                'DATA_DB__my_database__USER': 'postgres',
                'DATA_DB__my_database__PASSWORD': 'postgres',
                'DATA_DB__my_database__HOST': 'jupyteradminpostgres',
                'DATA_DB__my_database__PORT': '5432',
                'APPSTREAM_URL': 'https://url.to.appstream',
                'SUPPORT_URL': 'https://url.to.support/',
                'NOTEBOOKS_URL': 'https://url.to.notebooks/',
                'OAUTHLIB_INSECURE_TRANSPORT': '1',
            },
        )
        self.add_async_cleanup(cleanup_application)

        # Start a mock SSO
        number_of_times_at_sso = 0
        async def handle_authorize(request):
            # The user would login here, and eventually redirect back to redirect_uri
            nonlocal number_of_times_at_sso
            number_of_times_at_sso += 1
            state = request.query['state']
            code = 'some-code'
            return web.Response(status=302, headers={
                'Location': request.query['redirect_uri'] + f'?state={state}&code={code}',
            })

        tokens = iter(['token-1', 'token-2'])
        async def handle_token(_):
            return web.json_response({'access_token': next(tokens)}, status=200)

        async def handle_me(request):
            auth_header = request.headers['Authorization']

            if auth_header == 'Bearer token-1':
                return web.json_response({}, status=403)

            data = {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
            return web.json_response(data, status=200)
        sso_app = web.Application()
        sso_app.add_routes([
            web.get('/o/authorize/', handle_authorize),
            web.post('/o/token/', handle_token),
            web.get('/api/v1/user/me/', handle_me),
        ])
        sso_runner = web.AppRunner(sso_app)
        await sso_runner.setup()
        self.add_async_cleanup(sso_runner.cleanup)
        sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8005)
        await sso_site.start()

        await asyncio.sleep(2)

        session = aiohttp.ClientSession()
        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Make a request to the home page
        async with session.request('GET', 'http://localhost:8000/') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('JupyterLab', content)
        self.assertEqual(number_of_times_at_sso, 2)


class TestHttpWebsocketsProxy(unittest.TestCase):
    '''Tests that the proxy redirects to SSO, and can handle HTTP and websockets
    '''

    def add_async_cleanup(self, coroutine):
        loop = asyncio.get_event_loop()
        self.addCleanup(loop.run_until_complete, coroutine())

    @patch.dict(os.environ, {
        'PROXY_PORT': '8011',
        'UPSTREAM_ROOT': 'http://localhost:9000',
        'AUTHBROKER_CLIENT_ID': 'some-id',
        'AUTHBROKER_CLIENT_SECRET': 'some-secret',
        'AUTHBROKER_URL': 'http://localhost:8010/',
        'REDIS_URL': 'redis://analysis-workspace-redis:6379',
    })
    @async_test
    async def test_happy_path_behaviour(self):
        """Asserts on almost all of the happy path behaviour of the proxy,
        including redirection to and from SSO
        """
        proxy_task = asyncio.ensure_future(async_main())

        async def cleanup_proxy():
            proxy_task.cancel()
            await asyncio.sleep(0)
        self.add_async_cleanup(cleanup_proxy)

        # Start a mock SSO
        async def handle_authorize(request):
            # The user would login here, and eventually redirect back to redirect_uri
            state = request.query['state']
            code = 'some-code'
            return web.Response(status=302, headers={
                'Location': request.query['redirect_uri'] + f'?state={state}&code={code}',
            })

        async def handle_token(_):
            data = {
                'access_token': 'some-token'
            }
            return web.json_response(data, status=200, headers={
            })

        async def handle_me(_):
            data = {
                'email': 'test@test.com',
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
            }
            return web.json_response(data, status=200, headers={
            })
        sso_app = web.Application()
        sso_app.add_routes([
            web.get('/o/authorize/', handle_authorize),
            web.post('/o/token/', handle_token),
            web.get('/api/v1/user/me/', handle_me),
        ])
        sso_runner = web.AppRunner(sso_app)
        self.add_async_cleanup(sso_runner.cleanup)
        await sso_runner.setup()
        sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8010)
        await sso_site.start()

        # Start the upstream echo server
        async def handle_http(request):
            data = {
                'method': request.method,
                'content': (await request.read()).decode(),
                'headers': dict(request.headers),
            }
            return web.json_response(data, status=405, headers={
                'from-upstream': 'upstream-header-value',
            })

        async def handle_websockets(request):
            wsock = web.WebSocketResponse()
            await wsock.prepare(request)

            await wsock.send_str(json.dumps(dict(request.headers)))

            async for msg in wsock:
                if msg.type == aiohttp.WSMsgType.CLOSE:
                    await wsock.close()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await wsock.send_str(msg.data)
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await wsock.send_bytes(msg.data)

            return wsock

        upstream = web.Application()
        upstream.add_routes([
            web.get('/http', handle_http),
            web.patch('/http', handle_http),
            web.get('/websockets', handle_websockets),
        ])
        upstream_runner = web.AppRunner(upstream)
        await upstream_runner.setup()
        self.add_async_cleanup(upstream_runner.cleanup)
        upstream_site = web.TCPSite(upstream_runner, '0.0.0.0', 9000)
        await upstream_site.start()

        # There doesn't seem to be a way to wait for uvicorn start
        await asyncio.sleep(1)

        # Make a http request to the proxy
        session = aiohttp.ClientSession()

        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        async def sent_content():
            for _ in range(10000):
                yield b'Some content'

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {
            'from-downstream': 'downstream-header-value',
        }
        await asyncio.sleep(1)
        async with session.request(
                'GET', 'http://localhost:8011/http', headers=sent_headers) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(received_content['headers']['from-downstream'], 'downstream-header-value')
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # We are authorized by SSO, and can do non-GETs
        sent_headers = {
            'from-downstream': 'downstream-header-value',
        }
        async with session.request(
                'PATCH', 'http://localhost:8011/http',
                data=sent_content(), headers=sent_headers) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'PATCH')
        self.assertEqual(received_content['headers']['from-downstream'], 'downstream-header-value')
        self.assertEqual(received_content['content'], 'Some content'*10000)
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # Make a websockets connection to the proxy
        sent_headers = {
            'from-downstream-websockets': 'websockets-header-value',
        }
        async with session.ws_connect(
                'http://localhost:8011/websockets', headers=sent_headers) as wsock:
            msg = await wsock.receive()
            headers = json.loads(msg.data)

            await wsock.send_bytes(b'some-\0binary-data')
            msg = await wsock.receive()
            received_binary_content = msg.data

            await wsock.send_str('some-text-data')
            msg = await wsock.receive()
            received_text_content = msg.data

            await wsock.close()

        self.assertEqual(headers['from-downstream-websockets'], 'websockets-header-value')
        self.assertEqual(received_binary_content, b'some-\0binary-data')
        self.assertEqual(received_text_content, 'some-text-data')
