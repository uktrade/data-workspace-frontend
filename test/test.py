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
            },
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(4)

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
        self.assertIn(
            '<a class="govuk-link" href="http://testapplication-23b40dd9.localapps.com:8000/" style="font-weight: normal;">Test Application</a>', content)

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
        await cleanup_application_1()
        cleanup_application_2 = await create_application()
        self.add_async_cleanup(cleanup_application_2)

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
        async with session.request('GET', 'http://localapps.com:8000/admin') as response:
            content = await response.text()

        self.assertEqual(200, response.status)
        self.assertIn('This is the login page', content)

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
            },
        }
        sso_cleanup, number_of_times_at_sso = await create_sso(is_logged_in, codes, tokens, auth_to_me)
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

        self.assertIn(
            '<a class="govuk-link" href="http://testapplication-23b40dd9.localapps.com:8000/" style="font-weight: normal;">Test Application</a>', content)

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
            },
        }
        sso_cleanup, _ = await create_sso(is_logged_in, codes, tokens, auth_to_me)
        self.add_async_cleanup(sso_cleanup)

        await asyncio.sleep(6)

        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertNotIn('auth_user', content)

        async with session.request('GET', 'http://localapps.com:8000/table_data/my_database/public/auth_user') as response:
            content = await response.text()
            status = response.status

        self.assertEqual(status, 403)
        self.assertEqual(content, '')

        stdout, stderr, code = await give_user_database_perms()
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')
        self.assertEqual(code, 0)

        async with session.request('GET', 'http://localapps.com:8000/') as response:
            content = await response.text()

        self.assertIn('auth_user', content)

        async with session.request('GET', 'http://localapps.com:8000/table_data/my_database/public/auth_user') as response:
            content = await response.text()

        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(rows[0], ['id', 'password', 'last_login', 'is_superuser', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined'])
        self.assertEqual(rows[1][4], 'test@test.com')
        self.assertEqual(rows[2][0], 'Number of rows: 1')


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
    'APPLICATION_ROOT_DOMAIN': 'localapps.com:8000',
    'APPLICATION_TEMPLATES__1__NAME': 'testapplication',
    'APPLICATION_TEMPLATES__1__NICE_NAME': 'Test Application',
    'APPLICATION_TEMPLATES__1__SPAWNER': 'PROCESS',
    'APPLICATION_TEMPLATES__1__SPAWNER_OPTIONS__CMD__1': 'python3',
    'APPLICATION_TEMPLATES__1__SPAWNER_OPTIONS__CMD__2': '/test/echo_server.py',
}


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
        return web.Response(status=302, headers={
            'Location': request.query['redirect_uri'] + f'?state={state}&code={latest_code}',
        })

    async def handle_token(request):
        if (await request.post())['code'] != latest_code:
            return web.json_response({}, status=403)

        token = next(tokens)
        return web.json_response({'access_token': token}, status=200)

    async def handle_me(request):
        if request.headers['authorization'] in auth_to_me:
            return web.json_response(auth_to_me[request.headers['authorization']], status=200)

        return web.json_response({}, status=403)

    sso_app = web.Application()
    sso_app.add_routes([
        web.get('/o/authorize/', handle_authorize),
        web.post('/o/token/', handle_token),
        web.get('/api/v1/user/me/', handle_me),
    ])
    sso_runner = web.AppRunner(sso_app)
    await sso_runner.setup()
    sso_site = web.TCPSite(sso_runner, '0.0.0.0', 8005)
    await sso_site.start()

    def get_number_of_times():
        return number_of_times

    return sso_runner.cleanup, get_number_of_times


# Run the application proper in a way that is as possible to production
# The environment must be the same as in the Dockerfile
async def create_application():
    proc = await asyncio.create_subprocess_exec(
        '/app/start.sh',
        env=APP_ENV,
        preexec_fn=os.setsid,
    )

    async def _cleanup_application():
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)
        except ProcessLookupError:
            pass
    return _cleanup_application


async def flush_database():
    await (await asyncio.create_subprocess_shell(
        'django-admin flush --no-input --database default',
        env=APP_ENV,
    )).wait()


async def flush_redis():
    redis_client = await aioredis.create_redis('redis://analysis-workspace-redis:6379')
    await redis_client.execute('FLUSHDB')


async def give_user_app_perms():
    python_code = textwrap.dedent("""\
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
        """).encode('ascii')
    give_perm = await asyncio.create_subprocess_shell(
        'django-admin shell',
        env=APP_ENV,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_user_database_perms():
    python_code = textwrap.dedent("""\
        from django.contrib.auth.models import (
            User,
        )
        from app.models import (
            Database,
            Privilage,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        Privilage.objects.create(
            user=user,
            database=Database.objects.get(memorable_name="my_database"),
            schema="public",
            tables="auth_user",
        )
        """).encode('ascii')

    give_perm = await asyncio.create_subprocess_shell(
        'django-admin shell',
        env=APP_ENV,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code
