import asyncio
import logging
import os
import sys

import aiopg
from aiohttp import web


async def async_main():

    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ['aiohttp.server', 'aiohttp.web', 'aiohttp.access']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    pool = await aiopg.create_pool(os.environ['DATABASE_DSN__my_database'])

    async def handle_http(_):
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute('SELECT * FROM test_dataset')
                rows = [row[0] for row in await cur.fetchall()]

        return web.json_response({'data': rows}, status=200)

    upstream = web.Application()
    upstream.add_routes([web.get('/http', handle_http)])
    upstream_runner = web.AppRunner(upstream)
    await upstream_runner.setup()
    upstream_site = web.TCPSite(upstream_runner, '0.0.0.0', 8888)
    await upstream_site.start()
    await asyncio.Future()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())


if __name__ == '__main__':
    main()
