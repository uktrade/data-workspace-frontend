import asyncio
import logging
import os
import sys

from aiohttp import web


async def async_main():
    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ['aiohttp.server', 'aiohttp.web', 'aiohttp.access']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    async def handle_query_schema(request):
        database = request.match_info['database']
        schema = request.match_info['schema']

        logger.debug(database)
        logger.debug(schema)

        logger.debug(os.environ)
        dsn = os.environ[f'DATABASE_DSN__{database}']
        logger.debug(dsn)
        return web.json_response(
            {}, status=200, headers={'from-upstream': 'upstream-header-value'}
        )

    async def handle_http_get(request):
        data = {
            'content': (await request.read()).decode(),
            'headers': dict(request.headers),
        }

        return web.json_response(
            data, status=200, headers={'from-upstream': 'upstream-header-value'}
        )

    upstream = web.Application()

    upstream.add_routes(
        [
            web.get('/query_schema/{database}/{schema}', handle_query_schema),
            web.get('/get', handle_http_get),
        ]
    )

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
