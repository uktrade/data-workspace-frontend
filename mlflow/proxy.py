import asyncio
from base64 import urlsafe_b64decode
import json
import logging
import os
import random
import sys
import string
import time
import aiohttp
from aiohttp import web

from multidict import CIMultiDict
from yarl import URL

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'[{self.extra["context"]}] {msg}', kwargs


CONTEXT_ALPHABET = string.ascii_letters + string.digits


def b64_decode(b64_bytes):
    return urlsafe_b64decode(b64_bytes + (b"=" * ((4 - len(b64_bytes) % 4) % 4)))


async def async_main():
    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ["aiohttp.server", "aiohttp.web", "aiohttp.access", "proxy"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.addHandler(stdout_handler)

    port = int(os.environ["PROXY_PORT"])
    upstream_root = os.environ["UPSTREAM_ROOT"]
    mlflow_hostname = os.environ["MLFLOW_HOSTNAME"]
    public_key = load_pem_public_key(os.environ["JWT_PUBLIC_KEY"].encode())

    default_http_timeout = aiohttp.ClientTimeout()
    allowed_headers = (
        "x-scheme",
        "x-forwarded-proto",
        "referer",
        "user-agent",
        "content-length",
        "content-type",
        "authorization",
    )

    def get_random_context_logger():
        return ContextAdapter(logger, {"context": "".join(random.choices(CONTEXT_ALPHABET, k=8))})

    def without_transfer_encoding(request_or_response):
        return tuple(
            (key, value)
            for key, value in request_or_response.headers.items()
            if key.lower() != "transfer-encoding"
        )

    def headers_proxy(downstream_request):
        return tuple(
            (key, value)
            for key, value in downstream_request.headers.items()
            if key.lower() in allowed_headers
        )

    def request_scheme(request):
        return request.headers.get("x-forwarded-proto", request.url.scheme)

    def request_url(request):
        return str(request.url.with_scheme(request_scheme(request)))

    async def handle(downstream_request):
        method = downstream_request.method
        path = downstream_request.url.path
        query = downstream_request.url.query
        upstream_url = URL(upstream_root).with_path(path)

        if "Authorization" not in downstream_request.headers:
            return web.Response(status=401)

        jwt_token = downstream_request.headers["Authorization"][7:].encode()
        header_b64, payload_b64, signature_b64 = jwt_token.split(b".")
        payload = json.loads(b64_decode(payload_b64))

        try:
            public_key.verify(b64_decode(signature_b64), header_b64 + b"." + payload_b64)
        except InvalidSignature:
            return web.Response(status=401)

        now = time.time()
        if payload["exp"] <= now:
            return web.Response(status=401)

        if mlflow_hostname not in payload["authorised_hosts"]:
            return web.Response(status=401)

        return await handle_http(
            downstream_request,
            method,
            CIMultiDict(headers_proxy(downstream_request)),
            upstream_url,
            query,
            get_data(downstream_request),
            default_http_timeout,
        )

    def get_data(downstream_request):
        # Avoid aiohttp treating request as chunked unnecessarily, which works
        # for some upstream servers, but not all.

        # fmt: off
        return \
            b'' if (
                'content-length' not in downstream_request.headers
                and downstream_request.headers.get('transfer-encoding', '').lower() != 'chunked'
            ) else downstream_request.content
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
            downstream_response = web.StreamResponse(
                status=upstream_response.status,
                headers=CIMultiDict(
                    without_transfer_encoding(upstream_response) + response_headers
                ),
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

    async with aiohttp.ClientSession(
        auto_decompress=False,
        cookie_jar=aiohttp.DummyCookieJar(),
        skip_auto_headers=["Accept-Encoding"],
    ) as client_session:
        app = web.Application(
            middlewares=[
                server_logger(),
            ]
        )

        async def healthcheck(request):
            return web.Response(text="OK")

        app.add_routes(
            [web.get("/healthcheck", healthcheck)]
            + [
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

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        await asyncio.Future()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
