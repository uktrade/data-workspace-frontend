import asyncio

import base64
import hmac
import ipaddress
import json
import logging
import os
import random
import secrets
import sys
import string
import uuid
import urllib

import aiohttp
import ecs_logging
from aiohttp import web

from elasticapm.contrib.aiohttp import ElasticAPM
from hawkserver import authenticate_hawk_header
from multidict import CIMultiDict
from sentry_sdk import set_user
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from yarl import URL
from sentry import init_sentry
import redis.asyncio as redis

from dataworkspace.utils import normalise_environment
from proxy_session import SESSION_KEY, redis_session_middleware


class UserException(Exception):
    pass


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'[{self.extra["context"]}] {msg}', kwargs


PROFILE_CACHE_PREFIX = "data_workspace_profile"
CONTEXT_ALPHABET = string.ascii_letters + string.digits


async def async_main():
    env = normalise_environment(os.environ)

    stdout_handler = logging.StreamHandler(sys.stdout)
    local = "dataworkspace.test" in env["ALLOWED_HOSTS"]
    if not local:
        stdout_handler.setFormatter(
            ecs_logging.StdlibFormatter(exclude_fields=("log.original", "message"))
        )
    cookie_name = ("__Secure-" if not local else "") + "data_workspace_session"
    for logger_name in ["aiohttp.server", "aiohttp.web", "aiohttp.access", "proxy"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.addHandler(stdout_handler)

    port = int(env["PROXY_PORT"])
    admin_root = env["UPSTREAM_ROOT"]
    superset_root = env["SUPERSET_ROOT"]
    flower_root = env["FLOWER_ROOT"]
    hawk_senders = env["HAWK_SENDERS"]
    sso_base_url = env["AUTHBROKER_URL"]
    sso_host = URL(sso_base_url).host
    sso_client_id = env["AUTHBROKER_CLIENT_ID"]
    sso_client_secret = env["AUTHBROKER_CLIENT_SECRET"]
    redis_url = env["REDIS_URL"]
    root_domain = env["APPLICATION_ROOT_DOMAIN"]
    basic_auth_user = env["METRICS_SERVICE_DISCOVERY_BASIC_AUTH_USER"]
    basic_auth_password = env["METRICS_SERVICE_DISCOVERY_BASIC_AUTH_PASSWORD"]
    x_forwarded_for_trusted_hops = int(env["X_FORWARDED_FOR_TRUSTED_HOPS"])
    ip_allowlist_groups = env.get("APPLICATION_IP_ALLOWLIST_GROUPS", {})
    ip_allowlist = [
        ip_address for ip_addresses in ip_allowlist_groups.values() for ip_address in ip_addresses
    ] + env.get("APPLICATION_IP_WHITELIST", [])
    ga_tracking_id = env.get("GA_TRACKING_ID")
    mirror_remote_root = env["MIRROR_REMOTE_ROOT"]
    mirror_local_root = "/__mirror/"
    required_admin_headers = (
        "cookie",
        "host",
        "x-csrftoken",
        "x-data-workspace-no-modify-application-instance",
        "x-scheme",
        "x-forwarded-proto",
        "referer",
        "user-agent",
    )
    mlflow_port = int(env["MLFLOW_PORT"])

    # Cookies on the embed path must be allowed to be SameSite=None, so they
    # will be sent when the site is embedded in an iframe
    embed_path = "/visualisations/link"

    root_domain_no_port, _, root_port_str = root_domain.partition(":")
    try:
        root_port = int(root_port_str)
    except ValueError:
        root_port = None

    csp_common = "object-src 'none';"
    if root_domain not in ["dataworkspace.test:8000"]:
        csp_common += "upgrade-insecure-requests;"

    # A spawning application on <my-application>.<root_domain> shows the admin-styled site,
    # fetching assets from <root_domain>, but also makes requests to the current domain
    csp_application_spawning = csp_common + (
        f"default-src {root_domain};"
        f"base-uri {root_domain};"
        f"font-src {root_domain} data:  https://fonts.gstatic.com;"
        f"form-action {root_domain} *.{root_domain};"
        f"frame-ancestors {root_domain};"
        f"img-src {root_domain} data: https://www.googletagmanager.com https://www.google-analytics.com https://ssl.gstatic.com https://www.gstatic.com *.google-analytics.com *.googletagmanager.com;"  # pylint: disable=line-too-long
        f"script-src 'unsafe-inline' {root_domain} https://www.googletagmanager.com https://www.google-analytics.com https://tagmanager.google.com *.googletagmanager.com;"  # pylint: disable=line-too-long
        f"style-src 'unsafe-inline' {root_domain} https://tagmanager.google.com https://fonts.googleapis.com;"
        f"connect-src {root_domain} 'self' *.google-analytics.com *.analytics.google.com *.googletagmanager.com;"
    )

    # A running wrapped application on <my-application>.<root_domain>  has an
    # iframe that directly routes to the app on <my-application>--8888.<root_domain>
    def csp_application_running_wrapped(direct_host):
        return csp_common + (
            f"default-src 'none';"
            f"base-uri {root_domain};"
            f"form-action 'none';"
            f"frame-ancestors 'none';"
            f"frame-src {direct_host} {sso_host} https://www.googletagmanager.com;"
            f"img-src {root_domain} https://www.googletagmanager.com https://www.google-analytics.com https://ssl.gstatic.com https://www.gstatic.com *.google-analytics.com *.googletagmanager.com;"  # pylint: disable=line-too-long
            f"font-src {root_domain} data: https://fonts.gstatic.com;"
            f"script-src 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com https://tagmanager.google.com *.googletagmanager.com;"  # pylint: disable=line-too-long
            f"style-src 'unsafe-inline' {root_domain} https://tagmanager.google.com https://fonts.googleapis.com;"
            f"connect-src *.google-analytics.com *.analytics.google.com *.googletagmanager.com;"
        )

    # A running application should only connect to self: this is where we have the most
    # concern because we run the least-trusted code
    def csp_application_running_direct(host, public_host):
        return csp_common + (
            "default-src 'self';"
            "base-uri 'self';"
            # Safari does not have a 'self' for WebSockets
            f"connect-src 'self' wss://{host};"
            "font-src 'self' data:;"
            "form-action 'self';"
            f"frame-ancestors 'self' {root_domain} {public_host}.{root_domain};"
            "img-src 'self' data: blob:;"
            # Both JupyterLab and RStudio need `unsafe-eval`
            "script-src 'unsafe-inline' 'unsafe-eval' 'self' data:;"
            "style-src 'unsafe-inline' 'self' data:;"
            "worker-src 'self' blob:;"
        )

    redis_pool = await redis.from_url(redis_url)

    default_http_timeout = aiohttp.ClientTimeout()

    # When spawning and tring to detect if the app is running,
    # we fail quickly and often so a connection check is quick
    spawning_http_timeout = aiohttp.ClientTimeout(sock_read=5, sock_connect=2)

    def get_random_context_logger():
        return ContextAdapter(logger, {"context": "".join(random.choices(CONTEXT_ALPHABET, k=8))})

    def without_transfer_encoding(request_or_response):
        return tuple(
            (key, value)
            for key, value in request_or_response.headers.items()
            if key.lower() != "transfer-encoding"
        )

    def admin_headers_request(downstream_request):
        # When we make a deliberate request to the admin application from the
        # proxy we don't want to proxy content-length or content-type
        return (
            tuple(
                (key, value)
                for key, value in downstream_request.headers.items()
                if key.lower() in required_admin_headers
            )
            + downstream_request["sso_profile_headers"]
        )

    def admin_headers_proxy(downstream_request):
        return (
            tuple(
                (key, value)
                for key, value in downstream_request.headers.items()
                if key.lower() in required_admin_headers + ("content-length", "content-type")
            )
            + downstream_request["sso_profile_headers"]
        )

    def flower_headers_proxy(downstream_request):
        return (
            tuple(
                (key, value)
                for key, value in downstream_request.headers.items()
                if key.lower()
                in required_admin_headers + ("content-length", "content-type", "authorization")
            )
            + downstream_request["sso_profile_headers"]
        )

    def mlflow_headers_proxy(downstream_request, jwt):
        return tuple((key, value) for key, value in downstream_request.headers.items()) + (
            ("Authorization", f"Bearer {jwt}"),
        )

    def mirror_headers(downstream_request):
        return tuple(
            (key, value)
            for key, value in downstream_request.headers.items()
            if key.lower() not in ["host", "transfer-encoding"]
        )

    def application_headers(downstream_request):
        return (
            without_transfer_encoding(downstream_request)
            + (
                (("x-scheme", downstream_request.headers["x-forwarded-proto"]),)
                if "x-forwarded-proto" in downstream_request.headers
                else ()
            )
            + downstream_request["sso_profile_headers"]
        )

    async def superset_headers(downstream_request, path):
        credentials = {}
        dashboards = []

        if not path.startswith("/static/"):
            host_api_url = admin_root + "/api/v1/core/get-superset-role-credentials"

            async with client_session.request(
                "GET",
                host_api_url,
                headers=CIMultiDict(admin_headers_request(downstream_request)),
            ) as response:
                if response.status == 200:
                    response_json = await response.json()
                    credentials = response_json["credentials"]
                    dashboards = response_json["dashboards"]
                else:
                    raise UserException(
                        "Unable to fetch credentials for superset", response.status
                    )

        def standardise_header(header):
            # converts 'multi_word_header' to 'Multi-Word-Header'
            return "-".join([s.capitalize() for s in header.replace("_", "-").split("-")])

        return CIMultiDict(
            without_transfer_encoding(downstream_request)
            + (
                tuple(
                    [(f"Credentials-{standardise_header(k)}", v) for k, v in credentials.items()]
                )
            )
            + (tuple([("Dashboards", ",".join(dashboards))]))
            + downstream_request["sso_profile_headers"]
        )

    async def mlflow_jwt(downstream_request):
        host_api_url = admin_root + "/api/v1/core/generate-mlflow-jwt"
        async with client_session.request(
            "GET",
            host_api_url,
            headers=CIMultiDict(admin_headers_request(downstream_request)),
        ) as response:
            if response.status == 200:
                response_json = await response.json()
                jwt = response_json["jwt"]
            else:
                raise UserException("Unable to generate jwt for user", response.status)
        return jwt

    def is_service_discovery(request):
        return (
            request.url.path == "/api/v1/application"
            and request.url.host == root_domain_no_port
            and request.method == "GET"
        )

    def is_superset_requested(request):
        return (
            request.url.host == f"superset.{root_domain_no_port}"
            or request.url.host == f"superset-edit.{root_domain_no_port}"
            or request.url.host == f"superset-admin.{root_domain_no_port}"
        )

    def is_flower_requested(request):
        return request.url.host == f"flower.{root_domain_no_port}"

    def is_mlflow_requested(request):
        return request.url.host.split("--")[0] == "mlflow"

    def is_data_explorer_requested(request):
        return (
            request.url.path.startswith("/data-explorer/")
            and request.url.host == root_domain_no_port
        )

    def is_app_requested(request):
        return (
            request.url.host.endswith(f".{root_domain_no_port}")
            and not request.url.path.startswith(mirror_local_root)
            and not is_superset_requested(request)
            and not is_flower_requested(request)
            and not is_mlflow_requested(request)
        )

    def is_mirror_requested(request):
        return request.url.path.startswith(mirror_local_root)

    def is_requesting_credentials(request):
        return (
            request.url.host == root_domain_no_port
            and request.url.path == "/api/v1/aws_credentials"
        )

    def is_requesting_files(request):
        return request.url.host == root_domain_no_port and request.url.path == "/files"

    def is_dataset_requested(request):
        return (
            request.url.path.startswith("/api/v1/dataset/")
            or request.url.path.startswith("/api/v1/reference-dataset/")
            or request.url.path.startswith("/api/v1/eventlog/")
            or request.url.path.startswith("/api/v1/account/")
            or request.url.path.startswith("/api/v1/application-instance/")
            or request.url.path.startswith("/api/v1/core/")
        ) and request.url.host == root_domain_no_port

    def is_hawk_auth_required(request):
        return is_dataset_requested(request)

    def is_healthcheck_requested(request):
        return (
            request.url.path == "/healthcheck"
            and request.method == "GET"
            and not is_app_requested(request)
        )

    def is_table_requested(request):
        return (
            request.url.path.startswith("/api/v1/table/")
            and request.url.host == root_domain_no_port
            and request.method == "POST"
        )

    def is_peer_ip_required(request):
        # The healthcheck comes from the ALB, which doesn't send x-forwarded-for
        return not is_healthcheck_requested(request)

    def is_sso_auth_required(request):
        return (
            not is_healthcheck_requested(request)
            and not is_service_discovery(request)
            and not is_table_requested(request)
            and not is_dataset_requested(request)
        )

    def get_peer_ip(request):
        try:
            return (
                request.headers["x-forwarded-for"]
                .split(",")[-x_forwarded_for_trusted_hops]
                .strip()
            )
        except (KeyError, IndexError):
            return None

    def get_peer_ip_group(request):
        peer_ip = get_peer_ip(request)

        if peer_ip is None:
            return None

        for group, ip_addresses in ip_allowlist_groups.items():
            for address_or_subnet in ip_addresses:
                if ipaddress.IPv4Address(peer_ip) in ipaddress.IPv4Network(address_or_subnet):
                    return group

        return peer_ip

    def request_scheme(request):
        return request.headers.get("x-forwarded-proto", request.url.scheme)

    def request_url(request):
        return str(request.url.with_scheme(request_scheme(request)))

    async def handle(downstream_request):
        method = downstream_request.method
        path = downstream_request.url.path
        query = downstream_request.url.query
        app_requested = is_app_requested(downstream_request)
        mirror_requested = is_mirror_requested(downstream_request)
        superset_requested = is_superset_requested(downstream_request)
        flower_requested = is_flower_requested(downstream_request)
        mlflow_requested = is_mlflow_requested(downstream_request)

        # Websocket connections
        # - tend to close unexpectedly, both from the client and app
        # - don't need to show anything nice to the user on error
        is_websocket = (
            downstream_request.headers.get("connection", "").lower() == "upgrade"
            and downstream_request.headers.get("upgrade", "").lower() == "websocket"
        )

        try:
            if app_requested:
                return await handle_application(
                    is_websocket, downstream_request, method, path, query
                )
            if mirror_requested:
                return await handle_mirror(downstream_request, method, path)
            if superset_requested:
                return await handle_superset(downstream_request, method, path, query)
            if flower_requested:
                return await handle_flower(downstream_request, method, path, query)
            if mlflow_requested:
                return await handle_mlflow(downstream_request, method, path, query)
            return await handle_admin(
                downstream_request,
                method,
                CIMultiDict(admin_headers_proxy(downstream_request)),
                path,
                query,
                await get_data(downstream_request),
            )
        except Exception as exception:  # pylint: disable=broad-except
            user_exception = isinstance(exception, UserException)
            if not user_exception or (user_exception and exception.args[1] == 500):
                logger.exception(
                    "Exception during %s %s %s",
                    downstream_request.method,
                    downstream_request.url,
                    type(exception),
                )

            if is_websocket:
                raise

            params = {"message": exception.args[0]} if user_exception else {}
            status = exception.args[1] if user_exception else 500
            error_url = exception.args[2] if len(exception.args) > 2 else f"/error_{status}"
            error_qs = exception.args[3] if len(exception.args) > 3 else {}
            return await handle_http(
                downstream_request,
                "GET",
                CIMultiDict(admin_headers_request(downstream_request)),
                URL(admin_root).with_path(error_url).with_query(error_qs),
                params,
                b"",
                default_http_timeout,
            )

    async def handle_application(is_websocket, downstream_request, method, path, query):
        public_host, _, _ = downstream_request.url.host.partition(f".{root_domain_no_port}")
        possible_public_host, _, public_host_or_port_override = public_host.rpartition("--")
        try:
            port_override = int(public_host_or_port_override)
        except ValueError:
            port_override = None
        else:
            if 1 <= port_override <= 65535:
                public_host = possible_public_host
            else:
                port_override = None
        host_api_url = admin_root + "/api/v1/application/" + public_host
        host_html_path = "/tools/" + public_host

        async with client_session.request(
            "GET",
            host_api_url,
            headers=CIMultiDict(admin_headers_request(downstream_request)),
        ) as response:
            host_exists = response.status == 200
            application = await response.json()

        if response.status not in (200, 404):
            raise UserException(
                "Unable to start the application",
                response.status,
                "/error_403_visualisation",
                {"host": str(response.url).rsplit("/", maxsplit=1)[-1]},
            )

        if host_exists and application["state"] not in ["SPAWNING", "RUNNING"]:
            if "x-data-workspace-no-modify-application-instance" not in downstream_request.headers:
                async with client_session.request(
                    "DELETE",
                    host_api_url,
                    headers=CIMultiDict(admin_headers_request(downstream_request)),
                ) as delete_response:
                    await delete_response.read()
            raise UserException(
                "Application " + application["state"],
                500,
                "/error_500_application",
                {
                    "failure_message": "Application " + application["state"],
                    "application_id": application.get("id"),
                },
            )

        if not host_exists:
            if "x-data-workspace-no-modify-application-instance" not in downstream_request.headers:
                async with client_session.request(
                    "PUT",
                    host_api_url,
                    headers=CIMultiDict(admin_headers_request(downstream_request)),
                ) as response:
                    host_exists = response.status == 200
                    application = await response.json()
            else:
                raise UserException(
                    "Application stopped while starting",
                    500,
                    "/error_500_application",
                    {
                        "failure_message": "Application stopped while starting",
                        "application_id": None,
                    },
                )

        if response.status != 200:
            raise UserException(
                "Unable to start the application",
                500,
                "/error_500_application",
                {
                    "failure_message": "Unable to start the application",
                    "application_id": application.get("id"),
                },
            )

        if application["state"] not in ["SPAWNING", "RUNNING"]:
            raise UserException(
                f"Attempted to start the application, but it {application['state']}",
                500,
                "/error_500_application",
                {
                    "failure_message": f"Attempted to start the application, but it {application['state']}",
                    "application_id": application.get("id"),
                },
            )

        if not application["proxy_url"]:
            return await handle_http(
                downstream_request,
                "GET",
                CIMultiDict(admin_headers_request(downstream_request)),
                admin_root + host_html_path + "/spawning",
                {},
                b"",
                default_http_timeout,
                (("content-security-policy", csp_application_spawning),),
            )

        if is_websocket:
            return await handle_application_websocket(
                downstream_request, application["proxy_url"], path, query, port_override
            )

        if application["state"] == "SPAWNING":
            return await handle_application_http_spawning(
                downstream_request,
                method,
                application_upstream(application["proxy_url"], path, port_override),
                query,
                host_html_path,
                host_api_url,
                public_host,
            )

        if (
            application["state"] == "RUNNING"
            and application["wrap"] != "NONE"
            and not port_override
        ):
            return await handle_application_http_running_wrapped(
                downstream_request,
                application_upstream(application["proxy_url"], path, port_override),
                host_html_path,
                public_host,
            )

        return await handle_application_http_running_direct(
            downstream_request,
            method,
            application_upstream(application["proxy_url"], path, port_override),
            query,
            public_host,
        )

    async def handle_application_websocket(
        downstream_request, proxy_url, path, query, port_override
    ):
        upstream_url = application_upstream(proxy_url, path, port_override).with_query(query)
        return await handle_websocket(
            downstream_request,
            CIMultiDict(application_headers(downstream_request)),
            upstream_url,
        )

    def application_upstream(proxy_url, path, port_override):
        return (
            URL(proxy_url).with_path(path)
            if port_override is None
            else URL(proxy_url).with_path(path).with_port(port_override)
        )

    async def handle_application_http_spawning(
        downstream_request,
        method,
        upstream_url,
        query,
        host_html_path,
        host_api_url,
        public_host,
    ):
        host = downstream_request.headers["host"]
        try:
            logger.info("Spawning: Attempting to connect to %s", upstream_url)
            response = await handle_http(
                downstream_request,
                method,
                CIMultiDict(application_headers(downstream_request)),
                upstream_url,
                query,
                await get_data(downstream_request),
                spawning_http_timeout,
                # Although the application is spawning, if the response makes it back to the client,
                # we know the application is running, so we return the _running_ CSP headers
                (
                    (
                        "content-security-policy",
                        csp_application_running_direct(host, public_host),
                    ),
                ),
            )

        except Exception:  # pylint: disable=broad-except
            logger.info("Spawning: Failed to connect to %s", upstream_url)
            return await handle_http(
                downstream_request,
                "GET",
                CIMultiDict(admin_headers_request(downstream_request)),
                admin_root + host_html_path + "/spawning",
                {},
                b"",
                default_http_timeout,
                (("content-security-policy", csp_application_spawning),),
            )

        else:
            # Once a streaming response is done, if we have not yet returned
            # from the handler, it looks like aiohttp can cancel the current
            # task. We set RUNNING in another task to avoid it being cancelled
            async def set_application_running():
                async with client_session.request(
                    "PATCH",
                    host_api_url,
                    json={"state": "RUNNING"},
                    headers=CIMultiDict(admin_headers_request(downstream_request)),
                    timeout=default_http_timeout,
                ) as patch_response:
                    await patch_response.read()

            asyncio.ensure_future(set_application_running())

            return response

    async def handle_application_http_running_wrapped(
        downstream_request, upstream_url, host_html_path, public_host
    ):
        upstream = URL(upstream_url)
        direct_host = f"{public_host}--{upstream.port}.{root_domain}"
        return await handle_http(
            downstream_request,
            "GET",
            CIMultiDict(admin_headers_request(downstream_request)),
            admin_root + host_html_path + "/running",
            {},
            b"",
            default_http_timeout,
            (
                (
                    "content-security-policy",
                    csp_application_running_wrapped(direct_host),
                ),
            ),
        )

    async def handle_application_http_running_direct(
        downstream_request, method, upstream_url, query, public_host
    ):
        host = downstream_request.headers["host"]

        await send_to_google_analytics(downstream_request)

        return await handle_http(
            downstream_request,
            method,
            CIMultiDict(application_headers(downstream_request)),
            upstream_url,
            query,
            await get_data(downstream_request),
            default_http_timeout,
            (
                (
                    "content-security-policy",
                    csp_application_running_direct(host, public_host),
                ),
            ),
        )

    async def handle_mirror(downstream_request, method, path):
        mirror_path = path[len(mirror_local_root) :]
        upstream_url = URL(mirror_remote_root + mirror_path)
        return await handle_http(
            downstream_request,
            method,
            CIMultiDict(mirror_headers(downstream_request)),
            upstream_url,
            {},
            await get_data(downstream_request),
            default_http_timeout,
        )

    async def handle_superset(downstream_request, method, path, query):
        upstream_url = URL(superset_root).with_path(path)
        host = downstream_request.headers["host"]
        return await handle_http(
            downstream_request,
            method,
            await superset_headers(downstream_request, path),
            upstream_url,
            query,
            await get_data(downstream_request),
            default_http_timeout,
            (
                (
                    "content-security-policy",
                    csp_application_running_direct(host, "superset"),
                ),
            ),
        )

    async def handle_flower(downstream_request, method, path, query):
        upstream_url = URL(flower_root).with_path(path)
        return await handle_http(
            downstream_request,
            method,
            CIMultiDict(flower_headers_proxy(downstream_request)),
            upstream_url,
            query,
            await get_data(downstream_request),
            default_http_timeout,
        )

    async def handle_mlflow(downstream_request, method, path, query):
        jwt = await mlflow_jwt(downstream_request)
        internal_root = downstream_request.url.host.replace(
            f".{root_domain}", f"--internal.{root_domain}"
        )
        upstream_url = URL(
            f"{downstream_request.scheme}://{internal_root}:{mlflow_port}"
        ).with_path(path)

        return await handle_http(
            downstream_request,
            method,
            CIMultiDict(mlflow_headers_proxy(downstream_request, jwt)),
            upstream_url,
            query,
            await get_data(downstream_request),
            default_http_timeout,
        )

    async def handle_admin(downstream_request, method, headers, path, query, data):
        upstream_url = URL(admin_root).with_path(path)
        return await handle_http(
            downstream_request,
            method,
            headers,
            upstream_url,
            query,
            data,
            default_http_timeout,
        )

    async def handle_websocket(downstream_request, upstream_headers, upstream_url):
        protocol = downstream_request.headers.get("Sec-WebSocket-Protocol")
        protocols = (protocol,) if protocol else ()

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
                    str(upstream_url), headers=upstream_headers, protocols=protocols
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
                try:
                    await downstream_ws.close()
                except UnboundLocalError:
                    # If we didn't get to the line that creates `downstream_ws`
                    pass

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
            downstream_ws = await with_session_cookie(
                web.WebSocketResponse(protocols=protocols, heartbeat=30)
            )

            await downstream_ws.prepare(downstream_request)
            downstream_connection.set_result(downstream_ws)

            async for msg in downstream_ws:
                await proxy_msg(msg, upstream_ws)

        finally:
            upstream_task.cancel()

        return downstream_ws

    async def send_to_google_analytics(downstream_request):
        # Not perfect, but a good enough guide for usage
        _, extension = os.path.splitext(downstream_request.url.path)
        send_to_google = ga_tracking_id and extension in {
            "",
            ".doc",
            ".docx",
            ".html",
            ".pdf",
            ".ppt",
            ".pptx",
            ".xlsx",
            ".xlsx",
        }

        if not send_to_google:
            return

        async def _send():
            logger.info("Sending to Google Analytics %s...", downstream_request.url)
            peer_ip = get_peer_ip(downstream_request)

            response = await client_session.request(
                "POST",
                "https://www.google-analytics.com/collect",
                data={
                    "v": "1",
                    "tid": ga_tracking_id,
                    "cid": str(uuid.uuid4()),
                    "t": "pageview",
                    "uip": peer_ip,
                    "dh": downstream_request.url.host,
                    "dp": downstream_request.url.path_qs,
                    "ds": "data-workspace-server",
                    "dr": downstream_request.headers.get("referer", ""),
                    "ua": downstream_request.headers.get("user-agent", ""),
                },
                timeout=default_http_timeout,
            )
            logger.info("Sending to Google Analytics %s... %s", downstream_request.url, response)

        asyncio.create_task(_send())

    async def get_data(downstream_request):
        # Avoid aiohttp treating request as chunked unnecessarily, which works
        # for some upstream servers, but not all. Specifically RStudio drops
        # GET responses half way through if the request specified a chunked
        # encoding. AFAIK RStudio uses a custom webserver, so this behaviour
        # is not documented anywhere.

        # fmt: off
        return \
            b'' if (
                'content-length' not in downstream_request.headers
                and downstream_request.headers.get('transfer-encoding', '').lower() != 'chunked'
            ) else \
            await downstream_request.read() if downstream_request.content.at_eof() else \
            downstream_request.content
        # fmt: on

    async def handle_http(
        downstream_request,
        upstream_method,
        upstream_headers,
        upstream_url,
        upstream_query,
        upstream_data,
        timeout,
        response_headers=tuple(),
    ):
        async with client_session.request(
            upstream_method,
            str(upstream_url),
            params=upstream_query,
            headers=upstream_headers,
            data=upstream_data,
            allow_redirects=False,
            timeout=timeout,
        ) as upstream_response:
            _, _, _, with_session_cookie = downstream_request[SESSION_KEY]
            downstream_response = await with_session_cookie(
                web.StreamResponse(
                    status=upstream_response.status,
                    headers=CIMultiDict(
                        without_transfer_encoding(upstream_response) + response_headers
                    ),
                )
            )
            await downstream_response.prepare(downstream_request)
            async for chunk in upstream_response.content.iter_any():
                await downstream_response.write(chunk)

        return downstream_response

    def server_logger():
        @web.middleware
        async def _server_logger(request, handler):
            request_logger = get_random_context_logger()
            request["logger"] = request_logger
            url = request_url(request)

            request_logger.info(
                "Receiving (%s) (%s) (%s) (%s)",
                request.method,
                url,
                request.headers.get("User-Agent", "-"),
                request.headers.get("X-Forwarded-For", "-"),
            )

            response = await handler(request)

            request_logger.info(
                "Responding (%s) (%s) (%s) (%s) (%s) (%s)",
                request.method,
                url,
                request.headers.get("User-Agent", "-"),
                request.headers.get("X-Forwarded-For", "-"),
                response.status,
                response.content_length,
            )

            return response

        return _server_logger

    def require_peer_ip():
        @web.middleware
        async def _authenticate_by_peer_ip(request, handler):
            if not is_peer_ip_required(request):
                return await handler(request)

            peer_ip = get_peer_ip(request)

            if peer_ip is None:
                request["logger"].exception("No peer IP")
                return web.Response(status=500)

            return await handler(request)

        return _authenticate_by_peer_ip

    def authenticate_by_staff_sso():
        auth_path = "o/authorize/"
        token_path = "o/token/"
        me_path = "api/v1/user/me/"
        grant_type = "authorization_code"
        scope = "read write"
        response_type = "code"

        redirect_from_sso_path = "/__redirect_from_sso"
        session_token_key = "staff_sso_access_token"

        async def get_redirect_uri_authenticate(set_session_value, redirect_uri_final):
            scheme = URL(redirect_uri_final).scheme
            sso_state = await set_redirect_uri_final(set_session_value, redirect_uri_final)

            redirect_uri_callback = urllib.parse.quote(get_redirect_uri_callback(scheme), safe="")
            return (
                f"{sso_base_url}{auth_path}?"
                f"scope={scope}&state={sso_state}&"
                f"redirect_uri={redirect_uri_callback}&"
                f"response_type={response_type}&"
                f"client_id={sso_client_id}"
            )

        def get_redirect_uri_callback(scheme):
            return str(
                URL.build(
                    host=root_domain_no_port,
                    port=root_port,
                    scheme=scheme,
                    path=redirect_from_sso_path,
                )
            )

        async def set_redirect_uri_final(set_session_value, redirect_uri_final):
            session_key = secrets.token_hex(32)
            sso_state = urllib.parse.quote(f"{session_key}_{redirect_uri_final}", safe="")

            await set_session_value(session_key, redirect_uri_final)

            return sso_state

        async def get_redirect_uri_final(get_session_value, sso_state):
            session_key, _, state_redirect_url = urllib.parse.unquote(sso_state).partition("_")
            return state_redirect_url, await get_session_value(session_key)

        async def redirection_to_sso(
            with_new_session_cookie, set_session_value, redirect_uri_final
        ):
            return await with_new_session_cookie(
                web.Response(
                    status=302,
                    headers={
                        "Location": await get_redirect_uri_authenticate(
                            set_session_value, redirect_uri_final
                        )
                    },
                )
            )

        @web.middleware
        async def _authenticate_by_sso(request, handler):
            sso_auth_required = is_sso_auth_required(request)

            if not sso_auth_required:
                request.setdefault("sso_profile_headers", ())
                return await handler(request)

            get_session_value, set_session_value, with_new_session_cookie, _ = request[SESSION_KEY]

            token = await get_session_value(session_token_key)
            if request.path != redirect_from_sso_path and token is None:
                return await redirection_to_sso(
                    with_new_session_cookie, set_session_value, request_url(request)
                )

            if request.path == redirect_from_sso_path:
                code = request.query["code"]
                sso_state = request.query["state"]
                (
                    redirect_uri_final_from_url,
                    redirect_uri_final_from_session,
                ) = await get_redirect_uri_final(get_session_value, sso_state)

                if redirect_uri_final_from_url != redirect_uri_final_from_session:
                    # We might have been overtaken by a parallel request initiating another auth
                    # flow, and so another session. However, because we haven't retrieved the final
                    # URL from the session, we can't be sure that this is the same client that
                    # initiated this flow. However, we can redirect back to SSO
                    return await redirection_to_sso(
                        with_new_session_cookie,
                        set_session_value,
                        redirect_uri_final_from_url,
                    )

                async with client_session.post(
                    f"{sso_base_url}{token_path}",
                    data={
                        "grant_type": grant_type,
                        "code": code,
                        "client_id": sso_client_id,
                        "client_secret": sso_client_secret,
                        "redirect_uri": get_redirect_uri_callback(request_scheme(request)),
                    },
                ) as sso_response:
                    sso_response_json = await sso_response.json()
                await set_session_value(session_token_key, sso_response_json["access_token"])
                return await with_new_session_cookie(
                    web.Response(
                        status=302,
                        headers={"Location": redirect_uri_final_from_session},
                    )
                )

            # Get profile from Redis cache to avoid calling SSO on every request
            redis_profile_key = f"{PROFILE_CACHE_PREFIX}___{session_token_key}___{token}".encode(
                "ascii"
            )
            async with redis_pool as conn:
                me_profile_raw = await conn.get(redis_profile_key)
            me_profile = json.loads(me_profile_raw) if me_profile_raw else None

            async def handler_with_sso_headers():
                request["sso_profile_headers"] = (
                    ("sso-profile-email", me_profile["email"]),
                    # The default value of '' should be able to be removed after the cached
                    # profile in Redis without contact_email has expired, i.e. 60 seconds after
                    # deployment of this change
                    ("sso-profile-contact-email", me_profile.get("contact_email", "")),
                    (
                        "sso-profile-related-emails",
                        ",".join(me_profile.get("related_emails", [])),
                    ),
                    ("sso-profile-user-id", me_profile["user_id"]),
                    ("sso-profile-first-name", me_profile["first_name"]),
                    ("sso-profile-last-name", me_profile["last_name"]),
                )

                request["logger"].info(
                    "SSO-authenticated: %s %s %s",
                    me_profile["email"],
                    me_profile["user_id"],
                    request_url(request),
                )

                set_user({"id": me_profile["user_id"], "email": me_profile["email"]})

                return await handler(request)

            if me_profile:
                return await handler_with_sso_headers()

            request["logger"].info(
                "Making request to SSO - %s%s",
                sso_base_url,
                me_path,
            )
            async with client_session.get(
                f"{sso_base_url}{me_path}",
                headers={"Authorization": f"Bearer {token}"},
            ) as me_response:
                me_profile_full = await me_response.json() if me_response.status == 200 else None

            if not me_profile_full:
                return await redirection_to_sso(
                    with_new_session_cookie, set_session_value, request_url(request)
                )

            me_profile = {
                "email": me_profile_full["email"],
                "related_emails": me_profile_full["related_emails"],
                "contact_email": me_profile_full["contact_email"],
                "user_id": me_profile_full["user_id"],
                "first_name": me_profile_full["first_name"],
                "last_name": me_profile_full["last_name"],
            }
            async with redis_pool as conn:
                await conn.set(
                    redis_profile_key,
                    json.dumps(me_profile).encode("utf-8"),
                    ex=60,
                )

            return await handler_with_sso_headers()

        return _authenticate_by_sso

    def authenticate_by_basic_auth():
        @web.middleware
        async def _authenticate_by_basic_auth(request, handler):
            basic_auth_required = is_service_discovery(request)

            if not basic_auth_required:
                return await handler(request)

            if "Authorization" not in request.headers:
                return web.Response(status=401)

            basic_auth_prefix = "Basic "
            auth_value = (
                request.headers["Authorization"][len(basic_auth_prefix) :].strip().encode("ascii")
            )
            required_auth_value = base64.b64encode(
                f"{basic_auth_user}:{basic_auth_password}".encode("ascii")
            )

            if len(auth_value) != len(required_auth_value) or not hmac.compare_digest(
                auth_value, required_auth_value
            ):
                return web.Response(status=401)

            request["logger"].info("Basic-authenticated: %s", basic_auth_user)

            set_user({"id": basic_auth_user})

            return await handler(request)

        return _authenticate_by_basic_auth

    def authenticate_by_hawk_auth():
        async def lookup_credentials(sender_id):
            for hawk_sender in hawk_senders:
                if hawk_sender["id"] == sender_id:
                    return hawk_sender

        async def seen_nonce(nonce, sender_id):
            nonce_key = f"nonce-{sender_id}-{nonce}"
            async with redis_pool as conn:
                exists = await conn.exists(nonce_key)
                if not exists:
                    await conn.set(nonce_key, "1", ex=60)
                return exists

        @web.middleware
        async def _authenticate_by_hawk_auth(request, handler):
            hawk_auth_required = is_hawk_auth_required(request)

            if not hawk_auth_required:
                return await handler(request)

            try:
                authorization_header = request.headers["Authorization"]
            except KeyError:
                request["logger"].info("Hawk missing header")
                return web.Response(status=401)

            content = await request.read()

            error_message, creds = await authenticate_hawk_header(
                lookup_credentials,
                seen_nonce,
                15,
                authorization_header,
                request.method,
                request.url.host,
                request.url.port,
                request.url.path_qs,
                request.headers["Content-Type"],
                content,
            )
            if error_message is not None:
                request["logger"].info("Hawk unauthenticated: %s", error_message)
                return web.Response(status=401)

            request["logger"].info("Hawk authenticated: %s", creds["id"])

            set_user({"id": creds["id"]})

            return await handler(request)

        return _authenticate_by_hawk_auth

    def authenticate_by_ip_whitelist():
        @web.middleware
        async def _authenticate_by_ip_whitelist(request, handler):
            ip_whitelist_required = (
                is_app_requested(request)
                or is_superset_requested(request)
                or is_requesting_credentials(request)
                or is_requesting_files(request)
                or is_data_explorer_requested(request)
                or is_flower_requested(request)
            )

            if not ip_whitelist_required:
                return await handler(request)

            peer_ip = get_peer_ip(request)
            peer_ip_in_whitelist = any(
                ipaddress.IPv4Address(peer_ip) in ipaddress.IPv4Network(address_or_subnet)
                for address_or_subnet in ip_allowlist
            )

            if not peer_ip_in_whitelist:
                request["logger"].info("IP-whitelist unauthenticated: %s", peer_ip)
                return await handle_admin(
                    request,
                    "GET",
                    CIMultiDict(
                        admin_headers_request(request) + tuple([("x-forwarded-for", peer_ip)])
                    ),
                    "/error_403",
                    {},
                    b"",
                )

            request["logger"].info("IP-whitelist authenticated: %s", peer_ip)
            return await handler(request)

        return _authenticate_by_ip_whitelist

    async with aiohttp.ClientSession(
        auto_decompress=False,
        cookie_jar=aiohttp.DummyCookieJar(),
        skip_auto_headers=["Accept-Encoding"],
    ) as client_session:
        app = web.Application(
            middlewares=[
                server_logger(),
                require_peer_ip(),
                redis_session_middleware(
                    get_peer_ip_group, cookie_name, redis_pool, root_domain_no_port, embed_path
                ),
                authenticate_by_staff_sso(),
                authenticate_by_basic_auth(),
                authenticate_by_hawk_auth(),
                authenticate_by_ip_whitelist(),
            ]
        )
        app.add_routes(
            [
                getattr(web, method)(r"/{path:.*}", handle)
                for method in [
                    "delete",
                    "get",
                    "head",
                    "options",
                    "patch",
                    "post",
                    "put",
                ]
            ]
        )

        elastic_apm_url = env.get("ELASTIC_APM_URL")
        elastic_apm_secret_token = env.get("ELASTIC_APM_SECRET_TOKEN")
        elastic_apm = (
            {
                "SERVICE_NAME": "data-workspace",
                "SECRET_TOKEN": elastic_apm_secret_token,
                "SERVER_URL": elastic_apm_url,
                "ENVIRONMENT": env.get("ENVIRONMENT", "development"),
            }
            if elastic_apm_secret_token
            else {}
        )

        app["ELASTIC_APM"] = elastic_apm

        if elastic_apm:
            ElasticAPM(app)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        await asyncio.Future()


def main():
    init_sentry(integrations=[AioHttpIntegration()])

    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
