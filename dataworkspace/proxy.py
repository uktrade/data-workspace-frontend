import asyncio
import base64
import hmac
import ipaddress
import json
import logging
import os
import secrets
import sys
import urllib

import aiohttp
from aiohttp import web

import aioredis
from multidict import (
    CIMultiDict,
)
from yarl import (
    URL,
)
from hawkserver import authenticate_hawk_header

from dataworkspace.utils import (
    normalise_environment,
)
from proxy_session import (
    SESSION_KEY,
    redis_session_middleware,
)


class UserException(Exception):
    pass


PROFILE_CACHE_PREFIX = 'data_workspace_profile'


async def async_main():
    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ['aiohttp.server', 'aiohttp.web', 'aiohttp.access']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    env = normalise_environment(os.environ)
    port = int(env['PROXY_PORT'])
    admin_root = env['UPSTREAM_ROOT']
    sso_base_url = env['AUTHBROKER_URL']
    sso_client_id = env['AUTHBROKER_CLIENT_ID']
    sso_client_secret = env['AUTHBROKER_CLIENT_SECRET']
    redis_url = env['REDIS_URL']
    root_domain = env['APPLICATION_ROOT_DOMAIN']
    basic_auth_user = env['METRICS_SERVICE_DISCOVERY_BASIC_AUTH_USER']
    basic_auth_password = env['METRICS_SERVICE_DISCOVERY_BASIC_AUTH_PASSWORD']
    hawk_senders = env['HAWK_SENDERS']
    x_forwarded_for_trusted_hops = int(env['X_FORWARDED_FOR_TRUSTED_HOPS'])
    application_ip_whitelist = env['APPLICATION_IP_WHITELIST']

    root_domain_no_port, _, root_port_str = root_domain.partition(':')
    try:
        root_port = int(root_port_str)
    except ValueError:
        root_port = None

    redis_pool = await aioredis.create_redis_pool(redis_url)

    default_http_timeout = aiohttp.ClientTimeout()

    # When spawning and tring to detect if the app is running,
    # we fail quickly and often so a connection check is quick
    spawning_http_timeout = aiohttp.ClientTimeout(sock_read=5, sock_connect=2)

    def without_transfer_encoding(request_or_response):
        return CIMultiDict(tuple(
            (key, value) for key, value in request_or_response.headers.items()
            if key.lower() != 'transfer-encoding'
        ))

    def admin_headers(downstream_request):
        return CIMultiDict(
            tuple(without_transfer_encoding(downstream_request).items()) +
            downstream_request['sso_profile_headers']
        )

    def application_headers(downstream_request):
        return CIMultiDict(
            tuple(without_transfer_encoding(downstream_request).items()) +
            (
                (('x-scheme', downstream_request.headers['x-forwarded-proto']),) if 'x-forwarded-proto' in downstream_request.headers else
                ()
            )
        )

    def is_machine_to_machine(request):
        return '/api/v1/' in request.url.path and request.url.host == root_domain_no_port

    def is_service_discovery(request):
        return request.url.path == '/api/v1/application' and request.url.host == root_domain_no_port and request.method == 'GET'

    def is_app_requested(request):
        return request.url.host.endswith(f'.{root_domain_no_port}')

    def get_peer_ip(request):
        peer_ip = request.headers['x-forwarded-for'].split(',')[-x_forwarded_for_trusted_hops].strip()

        is_private = True
        try:
            is_private = ipaddress.ip_address(peer_ip).is_private
        except ValueError:
            is_private = False

        return peer_ip, is_private

    async def handle(downstream_request):
        method = downstream_request.method
        path = downstream_request.url.path
        query = downstream_request.url.query
        app_requested = is_app_requested(downstream_request)

        # Websocket connections
        # - tend to close unexpectedly, both from the client and app
        # - don't need to show anything nice to the user on error
        is_websocket = \
            downstream_request.headers.get('connection', '').lower() == 'upgrade' and \
            downstream_request.headers.get('upgrade', '').lower() == 'websocket'

        try:
            return \
                await handle_application(is_websocket, downstream_request, method, path, query) if app_requested else \
                await handle_admin(downstream_request, method, path, query)

        except Exception as exception:
            logger.exception('Exception during %s %s %s',
                             downstream_request.method, downstream_request.url, type(exception))

            if is_websocket:
                raise

            params = \
                {'message': exception.args[0]} if isinstance(exception, UserException) else \
                {}

            status = \
                exception.args[1] if isinstance(exception, UserException) else \
                500

            return await handle_http(downstream_request, 'GET', admin_headers(downstream_request), URL(admin_root).with_path(f'/error_{status}'), params, default_http_timeout)

    async def handle_application(is_websocket, downstream_request, method, path, query):
        public_host, _, _ = downstream_request.url.host.partition(f'.{root_domain_no_port}')
        host_api_url = admin_root + '/api/v1/application/' + public_host
        host_html_path = '/application/' + public_host

        async with client_session.request('GET', host_api_url, headers=admin_headers(downstream_request)) as response:
            host_exists = response.status == 200
            application = await response.json()

        if response.status != 200 and response.status != 404:
            raise UserException('Unable to start the application', response.status)

        if host_exists and application['state'] not in ['SPAWNING', 'RUNNING']:
            if 'x-data-workspace-no-modify-application-instance' not in downstream_request.headers:
                async with client_session.request(
                        'DELETE', host_api_url, headers=admin_headers(downstream_request),
                ) as delete_response:
                    await delete_response.read()
            raise UserException('Application ' + application['state'], 500)

        if not host_exists:
            if 'x-data-workspace-no-modify-application-instance' not in downstream_request.headers:
                async with client_session.request('PUT', host_api_url, headers=admin_headers(downstream_request)) as response:
                    host_exists = response.status == 200
                    application = await response.json()
            else:
                raise UserException('Application stopped while starting', 500)

        if response.status != 200:
            raise UserException('Unable to start the application', response.status)

        if application['state'] not in ['SPAWNING', 'RUNNING']:
            raise UserException(
                'Attempted to start the application, but it ' + application['state'], 500)

        if not application['proxy_url']:
            return await handle_http(downstream_request, 'GET', admin_headers(downstream_request), admin_root + host_html_path + '/spawning', {}, default_http_timeout)

        return \
            await handle_application_websocket(downstream_request, application['proxy_url'], path, query) if is_websocket else \
            await handle_application_http_spawning(downstream_request, method, application_upstream(application['proxy_url'], path), query, host_html_path, host_api_url) if application['state'] == 'SPAWNING' else \
            await handle_application_http_running(downstream_request, method, application_upstream(application['proxy_url'], path), query, host_api_url)

    async def handle_application_websocket(downstream_request, proxy_url, path, query):
        upstream_url = URL(proxy_url).with_path(path).with_query(query)
        return await handle_websocket(downstream_request, application_headers(downstream_request), upstream_url)

    def application_upstream(proxy_url, path):
        return URL(proxy_url).with_path(path)

    async def handle_application_http_spawning(downstream_request, method, upstream_url, query, host_html_path, host_api_url):
        try:
            logger.debug('Spawning: Attempting to connect to %s', upstream_url)
            response = await handle_http(downstream_request, method, application_headers(downstream_request), upstream_url, query, spawning_http_timeout)

        except Exception:
            logger.debug('Spawning: Failed to connect to %s', upstream_url)
            return await handle_http(downstream_request, 'GET', admin_headers(downstream_request), admin_root + host_html_path + '/spawning', {}, default_http_timeout)

        else:
            # Once a streaming response is done, if we have not yet returned
            # from the handler, it looks like aiohttp can cancel the current
            # task. We set RUNNING in another task to avoid it being cancelled
            async def set_application_running():
                async with client_session.request(
                        'PATCH', host_api_url, json={'state': 'RUNNING'}, headers=admin_headers(downstream_request), timeout=default_http_timeout,

                ) as patch_response:
                    await patch_response.read()
            asyncio.ensure_future(set_application_running())

            return response

    async def handle_application_http_running(downstream_request, method, upstream_url, query, _):
        # For the time being, we don't attempt to delete if an application has failed
        # Since initial attempts were too sensistive, and would delete the application
        # when it was still running
        # try:
        #     return await handle_http(downstream_request, method, headers, upstream_url, query, default_http_timeout)
        # except (aiohttp.client_exceptions.ClientConnectionError, asyncio.TimeoutError):
        # async with client_session.request('DELETE', host_api_url, headers=headers) as delete_response:
        #     await delete_response.read()
        #     raise

        return await handle_http(downstream_request, method, application_headers(downstream_request), upstream_url, query, default_http_timeout)

    async def handle_admin(downstream_request, method, path, query):
        upstream_url = URL(admin_root).with_path(path).with_query(query)
        return await handle_http(downstream_request, method, admin_headers(downstream_request), upstream_url, query, default_http_timeout)

    async def handle_websocket(downstream_request, upstream_headers, upstream_url):

        async def proxy_msg(msg, to_ws):
            if msg.type == aiohttp.WSMsgType.TEXT:
                await to_ws.send_str(msg.data)

            elif msg.type == aiohttp.WSMsgType.BINARY:
                await to_ws.send_bytes(msg.data)

            elif msg.type == aiohttp.WSMsgType.CLOSE:
                await to_ws.close()

            elif msg.type == aiohttp.WSMsgType.ERROR:
                await to_ws.close()

        async def upstream():
            try:
                async with client_session.ws_connect(
                        str(upstream_url),
                        headers=upstream_headers,
                ) as upstream_ws:
                    upstream_connection.set_result(upstream_ws)
                    downstream_ws = await downstream_connection
                    async for msg in upstream_ws:
                        await proxy_msg(msg, downstream_ws)
            except BaseException as exception:
                if not upstream_connection.done():
                    upstream_connection.set_exception(exception)
                raise
            finally:
                await downstream_ws.close()

        # This is slightly convoluted, but aiohttp documents that reading
        # from websockets should be done in the same task as the websocket was
        # created, so we read from downstream in _this_ task, and create
        # another task to connect to and read from the upstream socket. We
        # also need to make sure we wait for each connection before sending
        # data to it
        downstream_connection = asyncio.Future()
        upstream_connection = asyncio.Future()
        upstream_task = asyncio.ensure_future(upstream())

        try:
            upstream_ws = await upstream_connection
            _, _, _, with_session_cookie = downstream_request[SESSION_KEY]
            downstream_ws = await with_session_cookie(web.WebSocketResponse())

            await downstream_ws.prepare(downstream_request)
            downstream_connection.set_result(downstream_ws)

            async for msg in downstream_ws:
                await proxy_msg(msg, upstream_ws)
        finally:
            upstream_task.cancel()

        return downstream_ws

    async def handle_http(downstream_request, upstream_method, upstream_headers, upstream_url, upstream_query, timeout):
        # Avoid aiohttp treating request as chunked unnecessarily, which works
        # for some upstream servers, but not all. Specifically RStudio drops
        # GET responses half way through if the request specified a chunked
        # encoding. AFAIK RStudio uses a custom webserver, so this behaviour
        # is not documented anywhere.
        # This checks _read_bytes property of request and if it exists, uses _read_bytes to get data otherwise waits
        # for the request.content. The reason for this check is that we read the whole streamed response content to
        # authenticate request by hawk authentication. Refer to _authenticate_by_hawk function below line
        # 'content = await request.read()'
        data = (b'' if 'content-length' not in upstream_headers and
                downstream_request.headers.get('transfer-encoding', '').lower() != 'chunked' else
                downstream_request._read_bytes if downstream_request._read_bytes is not None else downstream_request.content)
        async with client_session.request(
                upstream_method, str(upstream_url),
                params=upstream_query,
                headers=upstream_headers,
                data=data,
                allow_redirects=False,
                timeout=timeout,
        ) as upstream_response:

            _, _, _, with_session_cookie = downstream_request[SESSION_KEY]
            downstream_response = await with_session_cookie(web.StreamResponse(
                status=upstream_response.status,
                headers=without_transfer_encoding(upstream_response),
            ))
            await downstream_response.prepare(downstream_request)
            async for chunk in upstream_response.content.iter_any():
                await downstream_response.write(chunk)

        return downstream_response

    def authenticate_by_staff_sso():

        auth_path = 'o/authorize/'
        token_path = 'o/token/'
        me_path = 'api/v1/user/me/'
        grant_type = 'authorization_code'
        scope = 'read write'
        response_type = 'code'

        redirect_from_sso_path = '/__redirect_from_sso'
        session_token_key = 'staff_sso_access_token'

        async def get_redirect_uri_authenticate(set_session_value, redirect_uri_final):
            scheme = URL(redirect_uri_final).scheme
            sso_state = await set_redirect_uri_final(set_session_value, redirect_uri_final)

            redirect_uri_callback = urllib.parse.quote(get_redirect_uri_callback(scheme), safe='')
            return f'{sso_base_url}{auth_path}?' \
                   f'scope={scope}&state={sso_state}&' \
                   f'redirect_uri={redirect_uri_callback}&' \
                   f'response_type={response_type}&' \
                   f'client_id={sso_client_id}'

        def request_scheme(request):
            return request.headers.get('x-forwarded-proto', request.url.scheme)

        def request_url(request):
            return str(request.url.with_scheme(request_scheme(request)))

        def get_redirect_uri_callback(scheme):
            return str(URL.build(
                host=root_domain_no_port,
                port=root_port,
                scheme=scheme,
                path=redirect_from_sso_path,
            ))

        async def set_redirect_uri_final(set_session_value, redirect_uri_final):
            session_key = secrets.token_hex(32)
            sso_state = urllib.parse.quote(f'{session_key}_{redirect_uri_final}', safe='')

            await set_session_value(session_key, redirect_uri_final)

            return sso_state

        async def get_redirect_uri_final(get_session_value, sso_state):
            session_key, _, state_redirect_url = urllib.parse.unquote(sso_state).partition('_')
            return state_redirect_url, await get_session_value(session_key)

        async def redirection_to_sso(with_new_session_cookie, set_session_value, redirect_uri_final):
            return await with_new_session_cookie(web.Response(status=302, headers={
                'Location': await get_redirect_uri_authenticate(set_session_value, redirect_uri_final),
            }))

        @web.middleware
        async def _authenticate_by_sso(request, handler):
            is_healthcheck = request.url.path == '/healthcheck' and request.method == 'GET' and not is_app_requested(
                request)
            sso_auth_required = (
                not is_healthcheck and
                not is_service_discovery(request) and
                not is_machine_to_machine(request)
            )

            if not sso_auth_required:
                request['sso_profile_headers'] = ()
                return await handler(request)

            get_session_value, set_session_value, with_new_session_cookie, _ = request[
                SESSION_KEY]

            token = await get_session_value(session_token_key)
            if request.path != redirect_from_sso_path and token is None:
                return await redirection_to_sso(with_new_session_cookie, set_session_value, request_url(request))

            if request.path == redirect_from_sso_path:
                code = request.query['code']
                sso_state = request.query['state']
                redirect_uri_final_from_url, redirect_uri_final_from_session = await get_redirect_uri_final(get_session_value, sso_state)

                if redirect_uri_final_from_url != redirect_uri_final_from_session:
                    # We might have been overtaken by a parallel request initiating another auth
                    # flow, and so another session. However, because we haven't retrieved the final
                    # URL from the session, we can't be sure that this is the same client that
                    # initiated this flow. However, we can redirect back to SSO
                    return await redirection_to_sso(with_new_session_cookie, set_session_value, redirect_uri_final_from_url)

                async with client_session.post(
                        f'{sso_base_url}{token_path}',
                        data={
                            'grant_type': grant_type,
                            'code': code,
                            'client_id': sso_client_id,
                            'client_secret': sso_client_secret,
                            'redirect_uri': get_redirect_uri_callback(request_scheme(request)),
                        },
                ) as sso_response:
                    sso_response_json = await sso_response.json()
                await set_session_value(session_token_key, sso_response_json['access_token'])
                return await with_new_session_cookie(web.Response(status=302, headers={'Location': redirect_uri_final_from_session}))

            # Get profile from Redis cache to avoid calling SSO on every request
            redis_profile_key = f'{PROFILE_CACHE_PREFIX}___{session_token_key}___{token}'.encode('ascii')
            with await redis_pool as conn:
                me_profile_raw = await conn.execute('GET', redis_profile_key)
            me_profile = json.loads(me_profile_raw) if me_profile_raw else None

            async def handler_with_sso_headers():
                request['sso_profile_headers'] = (
                    ('sso-profile-email', me_profile['email']),
                    ('sso-profile-user-id', me_profile['user_id']),
                    ('sso-profile-first-name', me_profile['first_name']),
                    ('sso-profile-last-name', me_profile['last_name']),
                )
                return await handler(request)

            if me_profile:
                return await handler_with_sso_headers()

            async with client_session.get(f'{sso_base_url}{me_path}', headers={
                    'Authorization': f'Bearer {token}'
            }) as me_response:
                me_profile_full = \
                    await me_response.json() if me_response.status == 200 else \
                    None

            if not me_profile_full:
                return await redirection_to_sso(with_new_session_cookie, set_session_value, request_url(request))

            me_profile = {
                'email': me_profile_full['email'],
                'user_id': me_profile_full['user_id'],
                'first_name': me_profile_full['first_name'],
                'last_name': me_profile_full['last_name'],
            }
            with await redis_pool as conn:
                await conn.execute('SET', redis_profile_key, json.dumps(me_profile).encode('utf-8'), 'EX', 60)

            return await handler_with_sso_headers()

        return _authenticate_by_sso

    def authenticate_by_basic_auth():
        @web.middleware
        async def _authenticate_by_basic_auth(request, handler):
            basic_auth_required = is_service_discovery(request)

            if not basic_auth_required:
                return await handler(request)

            if 'Authorization' not in request.headers:
                return web.Response(status=401)

            basic_auth_prefix = 'Basic '
            auth_value = request.headers['Authorization'][len(basic_auth_prefix):].strip().encode('ascii')
            required_auth_value = base64.b64encode(f'{basic_auth_user}:{basic_auth_password}'.encode('ascii'))

            if len(auth_value) != len(required_auth_value) or not hmac.compare_digest(auth_value, required_auth_value):
                return web.Response(status=401)

            return await handler(request)

        return _authenticate_by_basic_auth

    def authenticate_by_hawk_auth():

        async def lookup_credentials(sender_id):
            for hawk_sender in hawk_senders:
                if hawk_sender['id'] == sender_id:
                    return hawk_sender

        async def seen_nonce(nonce, sender_id):
            nonce_key = f'nonce-{sender_id}-{nonce}'
            with await redis_pool as conn:
                nonce_stored = await conn.execute('GET', nonce_key)
                if nonce_stored:
                    return True
                else:
                    return await conn.execute('SET', nonce_key, '1', 'EX', 5, 'NX')

        @web.middleware
        async def _authenticate_by_hawk_auth(request, handler):
            hawk_auth_required = is_machine_to_machine(request)

            if not hawk_auth_required:
                return await handler(request)

            # Read request content and store it in _read_bytes property to pass data to regarding endpoint after hawk
            # authentication.
            content = await request.read()

            is_authenticated, error_message, _ = await authenticate_hawk_header(
                lookup_credentials,
                seen_nonce,
                1000,
                request.headers['Authorization'],
                request.method,
                request.url.host,
                request.url.port,
                request.url.path,
                request.headers['Content-Type'],
                content,
            )
            if not is_authenticated:
                logger.debug('Hawk authentication failed.\nError message: %s', str(error_message))
                return web.Response(status=401)

            logger.debug('Hawk authentication succeeded')
            return await handler(request)

        return _authenticate_by_hawk_auth

    def authenticate_by_ip_whitelist():
        @web.middleware
        async def _authenticate_by_ip_whitelist(request, handler):
            ip_whitelist_required = is_app_requested(request)

            if not ip_whitelist_required:
                return await handler(request)

            logger.debug('Authenticating by ip whitelisting')
            peer_ip, _ = get_peer_ip(request)
            peer_ip_in_whitelist = any(
                ipaddress.IPv4Address(peer_ip) in ipaddress.IPv4Network(address_or_subnet)
                for address_or_subnet in application_ip_whitelist
            )

            if not peer_ip_in_whitelist:
                logger.debug('Authentication by ip whitelisting failed')
                return await handle_admin(request, 'GET', '/error_403', {})

            return await handler(request)

        return _authenticate_by_ip_whitelist

    async with aiohttp.ClientSession(auto_decompress=False, cookie_jar=aiohttp.DummyCookieJar()) as client_session:
        app = web.Application(middlewares=[
            redis_session_middleware(redis_pool, root_domain_no_port),
            authenticate_by_staff_sso(),
            authenticate_by_basic_auth(),
            authenticate_by_hawk_auth(),
            authenticate_by_ip_whitelist(),
        ])
        app.add_routes([
            getattr(web, method)(r'/{path:.*}', handle)
            for method in ['delete', 'get', 'head', 'options', 'patch', 'post', 'put']
        ])

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        await asyncio.Future()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == '__main__':
    main()
