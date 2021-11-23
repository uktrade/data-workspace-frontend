import asyncio
import logging
import os
import sys

import aiohttp
from aiohttp import web


async def async_main(port, url):
    async def handle_healthcheck(_):
        async with aiohttp.ClientSession() as client_session:
            async with client_session.get(url) as response:
                response = await response.text()
                return web.Response(text=response)

    async def handle_healthcheck_alb(_):
        return web.Response(text="OK")

    app = web.Application()
    app.add_routes(
        [
            web.get("/check", handle_healthcheck),
            web.get("/check_alb", handle_healthcheck_alb),
        ]
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


def main():
    port = int(os.environ["PORT"])
    url = os.environ["URL"]

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    loop = asyncio.get_event_loop()
    loop.create_task(async_main(port, url))
    loop.run_forever()


if __name__ == "__main__":
    main()
