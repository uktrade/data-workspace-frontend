import asyncio
import json
import logging
import sys

import aiohttp
from aiohttp import web


async def async_main():

    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ["aiohttp.server", "aiohttp.web", "aiohttp.access"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    async def handle_http(request):
        data = {
            "method": request.method,
            "content": (await request.read()).decode(),
            "headers": dict(request.headers),
        }
        return web.json_response(
            data,
            status=405,
            headers={
                "from-upstream": "upstream-header-value",
                "Set-Cookie": "test-set-cookie",
            },
        )

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
    upstream.add_routes(
        [
            web.get("/http", handle_http),
            web.patch("/http", handle_http),
            web.get("/websockets", handle_websockets),
        ]
    )
    upstream_runner = web.AppRunner(upstream)
    await upstream_runner.setup()
    upstream_site = web.TCPSite(upstream_runner, "0.0.0.0", 8888)
    await upstream_site.start()
    await asyncio.Future()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == "__main__":
    main()
