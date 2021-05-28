import asyncio
import logging
import os
import sys
from http import HTTPStatus

import aiopg
import psycopg2.sql
from aiohttp import web


async def async_main():
    stdout_handler = logging.StreamHandler(sys.stdout)
    for logger_name in ['aiohttp.server', 'aiohttp.web', 'aiohttp.access']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)

    async def handle_schema_dataset(request):
        database = request.match_info['database']
        schema = request.match_info['schema']
        table = request.match_info['table']

        dsn = os.environ[f'DATABASE_DSN__{database}']

        sql = psycopg2.sql.SQL('SELECT * FROM {}.{}').format(
            psycopg2.sql.Identifier(schema), psycopg2.sql.Identifier(table)
        )

        async with aiopg.create_pool(dsn) as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql)
                    rows = [row[0] for row in await cur.fetchall()]

        return web.json_response(
            {
                'database': database,
                'schema': schema,
                'table': table,
                'dsn': dsn,
                'data': rows,
            },
            status=HTTPStatus.OK,
            headers={},
        )

    async def handle_query_schema(request):
        return web.json_response(
            {}, status=200, headers={'from-upstream': 'upstream-header-value'}
        )

    upstream = web.Application()
    upstream.add_routes([web.get('/query_schema/{schema_name}', handle_query_schema)])

    upstream.add_routes(
        [web.get('/query_data/{database}/{schema}/{table}', handle_schema_dataset)]
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
