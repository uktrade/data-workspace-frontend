import asyncio
import json
import os
import signal
import textwrap
import unittest

import aiohttp
from aiohttp import web


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
        proc = None

        await flush_database()

        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)

        async def create_application():
            nonlocal proc
            proc = await asyncio.create_subprocess_exec(
                '/app/start.sh',
                env=APP_ENV,
                preexec_fn=os.setsid,
            )
        await create_application()
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

        await asyncio.sleep(4)

        session = aiohttp.ClientSession()

        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Ensure the user doesn't see the application link since they don't
        # have permission
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()
        self.assertNotIn('Test Application', content)

        # Ensure we sent the right thing to SSO
        self.assertEqual('some-code', token_request_code)
        self.assertEqual('Bearer some-token', me_request_auth)

        # Give the user permission
        code = textwrap.dedent("""\
            from django.contrib.auth.models import (
                Permission,
            )
            from django.contrib.auth.models import (
                User,
            )
            from django.contrib.contenttypes.models import (
                ContentType,
            )
            from app.models import (
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
            env=APP_ENV,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await give_perm.communicate(code)
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        code = await give_perm.wait()
        self.assertEqual(code, 0)

        # Make a request to the home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        # Ensure the user sees the link to the application
        self.assertEqual(200, response.status)
        self.assertIn(
            '<a class="govuk-link" href="http://testapplication-23b40dd9.localapps.com:8000/" style="font-weight: normal;">Test Application</a>', content)

        async with session.request('GET', 'http://testapplication-23b40dd9.localapps.com:8000/') as response:
            application_content_1 = await response.text()

        # The tests are not isolated from each other in the database, so we may have a running
        # one that is "errored" from a previous run
        if 'Application STOPPED' in application_content_1:
            async with session.request('GET', 'http://testapplication-23b40dd9.localapps.com:8000/') as response:
                application_content_1 = await response.text()

        self.assertIn('Starting Test Application', application_content_1)

        async with session.request('GET', 'http://testapplication-23b40dd9.localapps.com:8000/') as response:
            application_content_2 = await response.text()

        self.assertIn('Starting Test Application', application_content_2)

        # There are forced sleeps in starting a process
        await asyncio.sleep(6)

        # The initial connection has to be a GET, since these are redirected
        # to SSO. Unsure initial connection being a non-GET is a feature that
        # needs to be supported / what should happen in this case
        sent_headers = {
            'from-downstream': 'downstream-header-value',
        }

        async with session.request(
                'GET', 'http://testapplication-23b40dd9.localapps.com:8000/http', headers=sent_headers) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(received_content['headers']['from-downstream'], 'downstream-header-value')
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # We are authorized by SSO, and can do non-GETs
        async def sent_content():
            for _ in range(10000):
                yield b'Some content'
        sent_headers = {
            'from-downstream': 'downstream-header-value',
        }
        async with session.request(
                'PATCH', 'http://testapplication-23b40dd9.localapps.com:8000/http',
                data=sent_content(), headers=sent_headers) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'PATCH')
        self.assertEqual(received_content['headers']['from-downstream'], 'downstream-header-value')
        self.assertEqual(received_content['content'], 'Some content'*10000)
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

        # Assert that transfer-encoding does not become chunked unnecessarily
        async with session.request(
                'GET', 'http://testapplication-23b40dd9.localapps.com:8000/http') as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)

        async with session.request(
                'PATCH', 'http://testapplication-23b40dd9.localapps.com:8000/http', data=b'1234') as response:
            received_content = await response.json()
        header_keys = [key.lower() for key in received_content['headers'].keys()]
        self.assertNotIn('transfer-encoding', header_keys)
        self.assertEqual(received_content['content'], '1234')

        # Make a websockets connection to the proxy
        sent_headers = {
            'from-downstream-websockets': 'websockets-header-value',
        }
        async with session.ws_connect(
                'http://testapplication-23b40dd9.localapps.com:8000/websockets', headers=sent_headers) as wsock:
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

        # Test that if we will the application, and restart, we initially
        # see an error that the application stopped, but then after refresh
        # we load up the application succesfully
        await cleanup_application()
        await create_application()

        await asyncio.sleep(6)

        async with session.request('GET', 'http://testapplication-23b40dd9.localapps.com:8000/') as response:
            error_content = await response.text()

        self.assertIn('Application STOPPED', error_content)

        async with session.request('GET', 'http://testapplication-23b40dd9.localapps.com:8000/') as response:
            content = await response.text()

        self.assertIn('Starting Test Application', content)
        await asyncio.sleep(6)

        sent_headers = {
            'from-downstream': 'downstream-header-value',
        }
        async with session.request(
                'GET', 'http://testapplication-23b40dd9.localapps.com:8000/http', headers=sent_headers) as response:
            received_content = await response.json()
            received_headers = response.headers

        # Assert that we received the echo
        self.assertEqual(received_content['method'], 'GET')
        self.assertEqual(received_content['headers']['from-downstream'], 'downstream-header-value')
        self.assertEqual(received_headers['from-upstream'], 'upstream-header-value')

    @async_test
    async def test_application_redirects_to_sso_if_initially_not_authorized(self):
        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)
        proc = await asyncio.create_subprocess_exec(
            '/app/start.sh',
            env=APP_ENV,
            preexec_fn=os.setsid,
        )
        self.add_async_cleanup(cleanup_application)

        # Start a limited mock SSO
        async def handle_authorize(_):
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

        await asyncio.sleep(6)

        session = aiohttp.ClientSession()

        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Make a request to the application home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

        # Make a request to the application admin page
        async with session.request('GET', 'http://localapps.com:8000/admin') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

    @async_test
    async def test_application_redirects_to_sso_again_if_token_expired(self):
        # Run the application proper in a way that is as possible to production
        # The environment must be the same as in the Dockerfile
        async def cleanup_application():
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)

        await flush_database()

        proc = await asyncio.create_subprocess_exec(
            '/app/start.sh',
            env=APP_ENV,
            preexec_fn=os.setsid,
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

        await asyncio.sleep(6)

        session = aiohttp.ClientSession()

        async def cleanup_session():
            await session.close()
            await asyncio.sleep(0.25)
        self.add_async_cleanup(cleanup_session)

        # Make a request to the home page
        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertEqual(number_of_times_at_sso, 2)
        self.assertEqual(200, response.status)

        # Give the user permission
        code = textwrap.dedent("""\
            from django.contrib.auth.models import (
                Permission,
            )
            from django.contrib.auth.models import (
                User,
            )
            from django.contrib.contenttypes.models import (
                ContentType,
            )
            from app.models import (
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
            env=APP_ENV,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await give_perm.communicate(code)
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        code = await give_perm.wait()
        self.assertEqual(code, 0)

        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertIn(
            '<a class="govuk-link" href="http://testapplication-23b40dd9.localapps.com:8000/" style="font-weight: normal;">Test Application</a>', content)


APP_ENV = {
    # Static: as in Dockerfile
    'PYTHONPATH': '/app',
    'DJANGO_SETTINGS_MODULE': 'app.settings',
    # Dynamic: proxy and app settings populated at runtime
    'AUTHBROKER_CLIENT_ID': 'some-id',
    'AUTHBROKER_CLIENT_SECRET': 'some-secret',
    'AUTHBROKER_URL': 'http://localhost:8005/',
    'REDIS_URL': 'redis://analysis-workspace-redis:6379',
    'SECRET_KEY': 'localhost',
    'ALLOWED_HOSTS__1': 'localapps.com',
    'ALLOWED_HOSTS__2': '.localapps.com',
    'ADMIN_DB__NAME': 'postgres',
    'ADMIN_DB__USER': 'postgres',
    'ADMIN_DB__PASSWORD': 'postgres',
    'ADMIN_DB__HOST': 'analysis-workspace-postgres',
    'ADMIN_DB__PORT': '5432',
    'DATA_DB__my_database__NAME': 'postgres',
    'DATA_DB__my_database__USER': 'postgres',
    'DATA_DB__my_database__PASSWORD': 'postgres',
    'DATA_DB__my_database__HOST': 'analysis-workspace-postgres',
    'DATA_DB__my_database__PORT': '5432',
    'APPSTREAM_URL': 'https://url.to.appstream',
    'SUPPORT_URL': 'https://url.to.support/',
    'NOTEBOOKS_URL': 'https://url.to.notebooks/',
    'OAUTHLIB_INSECURE_TRANSPORT': '1',
    'APPLICATION_ROOT_DOMAIN': 'localapps.com:8000',
    'APPLICATION_TEMPLATES__1__NAME': 'testapplication',
    'APPLICATION_TEMPLATES__1__NICE_NAME': 'Test Application',
    'APPLICATION_TEMPLATES__1__SPAWNER': 'PROCESS',
    'APPLICATION_TEMPLATES__1__SPAWNER_OPTIONS__CMD__1': 'python3',
    'APPLICATION_TEMPLATES__1__SPAWNER_OPTIONS__CMD__2': '/test/echo_server.py',
}


async def flush_database():
    await (await asyncio.create_subprocess_shell(
        'django-admin flush --no-input --database default',
        env=APP_ENV,
    )).wait()
