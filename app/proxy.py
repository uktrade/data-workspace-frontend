import asyncio
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

from session import (
    SESSION_KEY,
    redis_session_middleware,
)


async def async_main():
    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ['aiohttp.server', 'aiohttp.web', 'aiohttp.access']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    port = int(os.environ['PROXY_PORT'])
    upstream_root = os.environ['UPSTREAM_ROOT']
    sso_base_url = os.environ['AUTHBROKER_URL']
    sso_client_id = os.environ['AUTHBROKER_CLIENT_ID']
    sso_client_secret = os.environ['AUTHBROKER_CLIENT_SECRET']
    redis_url = os.environ['REDIS_URL']

    redis_pool = await aioredis.create_redis_pool(redis_url)

    def without_transfer_encoding(headers):
        return tuple(
            (key, value) for key, value in headers.items()
            if key.lower() != 'transfer-encoding'
        )

    async def handle(downstream_request):
        upstream_url = URL(upstream_root) \
            .with_path(downstream_request.url.path) \
            .with_query(downstream_request.url.query)
        is_websocket = \
            downstream_request.headers.get('connection', '').lower() == 'upgrade' and \
            downstream_request.headers.get('upgrade', '').lower() == 'websocket'

        return \
            await handle_websocket(upstream_url, downstream_request) if is_websocket else \
            await handle_http(upstream_url, downstream_request)

    async def handle_websocket(upstream_url, downstream_request):

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
                        headers=CIMultiDict(
                            without_transfer_encoding(downstream_request.headers) +
                            downstream_request['sso_profile_headers']
                        ),
                ) as upstream_ws:
                    upstream_connection.set_result(upstream_ws)
                    downstream_ws = await downstream_connection
                    async for msg in upstream_ws:
                        await proxy_msg(msg, downstream_ws)
            except BaseException as exception:
                if not upstream_connection.done():
                    upstream_connection.set_exception(exception)
                raise

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
            downstream_ws = web.WebSocketResponse()
            await downstream_ws.prepare(downstream_request)
            downstream_connection.set_result(downstream_ws)

            async for msg in downstream_ws:
                await proxy_msg(msg, upstream_ws)
        finally:
            upstream_task.cancel()

        return downstream_ws

    async def handle_http(upstream_url, downstream_request):
        async with client_session.request(
                downstream_request.method, str(upstream_url),
                params=downstream_request.url.query,
                headers=CIMultiDict(
                    without_transfer_encoding(downstream_request.headers) +
                    downstream_request['sso_profile_headers']
                ),
                data=downstream_request.content,
        ) as upstream_response:

            _, _, _, with_session_cookie = downstream_request[SESSION_KEY]
            downstream_response = await with_session_cookie(web.StreamResponse(
                status=upstream_response.status,
                headers=CIMultiDict(without_transfer_encoding(upstream_response.headers)),
            ))
            await downstream_response.prepare(downstream_request)
            while True:
                chunk = await upstream_response.content.readany()
                if chunk:
                    await downstream_response.write(chunk)
                else:
                    break

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

        async def get_redirect_uri_authenticate(set_session_value, request):
            state = secrets.token_urlsafe(32)
            await set_redirect_uri_final(set_session_value, state, request)
            redirect_uri_callback = urllib.parse.quote(get_redirect_uri_callback(request), safe='')
            return f'{sso_base_url}{auth_path}?' \
                   f'scope={scope}&state={state}&' \
                   f'redirect_uri={redirect_uri_callback}&' \
                   f'response_type={response_type}&' \
                   f'client_id={sso_client_id}'

        def get_redirect_uri_callback(request):
            scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
            uri = request.url.with_scheme(scheme) \
                             .with_path(redirect_from_sso_path) \
                             .with_query({})
            return str(uri)

        async def set_redirect_uri_final(set_session_value, state, request):
            scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
            await set_session_value(state, str(request.url.with_scheme(scheme)))

        async def get_redirect_uri_final(get_session_value, request):
            state = request.query['state']
            return await get_session_value(state)

        @web.middleware
        async def _authenticate_by_sso(request, handler):
            # Database authentication is handled by the django app
            if request.url.path in ['/healthcheck', '/api/v1/databases']:
                request['sso_profile_headers'] = ()
                return await handler(request)

            get_session_value, set_session_value, with_new_session_cookie, with_session_cookie = request[SESSION_KEY]

            token = await get_session_value(session_token_key)
            if request.path != redirect_from_sso_path and token is None:
                location = await get_redirect_uri_authenticate(set_session_value, request)
                return await with_session_cookie(web.Response(status=302, headers={
                    'Location': location,
                }))

            if request.path == redirect_from_sso_path:
                code = request.query['code']
                redirect_uri_final = await get_redirect_uri_final(get_session_value, request)

                # If there isn't a redirect_uri_final, we might...
                # - not be the same client as made the original request, and so should not proceed
                # - be the same client, but have been overtaken by another concurrent login that
                #   created a new session after its login, and so this request was made with that
                #   new session
                # We might have been redirected attempting to access a static asset, so we don't
                # redirect to any particular HTML page, since it would be broken to "succeed" by
                # returning something that wasn't asked for
                if redirect_uri_final is None:
                    return web.Response(status=401)

                sso_response = await client_session.post(
                    f'{sso_base_url}{token_path}',
                    data={
                        'grant_type': grant_type,
                        'code': code,
                        'client_id': sso_client_id,
                        'client_secret': sso_client_secret,
                        'redirect_uri': get_redirect_uri_callback(request),
                    },
                )
                await set_session_value(session_token_key, (await sso_response.json())['access_token'])
                # A new session cookie to migitate session fixation attack
                return await with_new_session_cookie(web.Response(status=302, headers={'Location': redirect_uri_final}))

            async with client_session.get(f'{sso_base_url}{me_path}', headers={
                    'Authorization': f'Bearer {token}'
            }) as me_response:
                me_profile = await me_response.json()

            async def handler_with_sso_headers():
                request['sso_profile_headers'] = (
                    ('sso-profile-email', me_profile['email']),
                    ('sso-profile-user-id', me_profile['user_id']),
                    ('sso-profile-first-name', me_profile['first_name']),
                    ('sso-profile-last-name', me_profile['last_name']),
                )
                return await handler(request)

            return \
                await handler_with_sso_headers() if me_response.status == 200 else \
                await with_session_cookie(web.Response(status=302, headers={
                    'Location': await get_redirect_uri_authenticate(set_session_value, request),
                }))

        return _authenticate_by_sso

    # Although less efficient, paranoia-avoid errors when the application is
    # closing keep-alive connections, and mitigates running out of file
    # handles. Could be changed, but KISS
    conn = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=conn) as client_session:
        app = web.Application(middlewares=[
            redis_session_middleware(redis_pool),
            authenticate_by_staff_sso(),
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
