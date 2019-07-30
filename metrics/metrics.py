import asyncio
import json
import logging
import os
import sys
import textwrap

import aiohttp
from aiohttp import (
    web,
)


async def async_main(logger, port, url):

    async def handle_metrics(_):
        async with aiohttp.ClientSession() as client_session:
            async with client_session.get(url) as response:
                task_metrics = json.loads(await response.text())
                logger.debug(task_metrics)
                app_container_metrics = [
                    container_metrics
                    for _, container_metrics in task_metrics.items()
                    if '-metrics-' not in container_metrics['name'] and '-internalecspause-' not in container_metrics['name'] and '-s3sync-' not in container_metrics['name']
                ][0]

                prometheus_format_metrics = textwrap.dedent(f'''\
                    memory_stats__usage {app_container_metrics['memory_stats']['usage']}
                    precpu_stats__cpu_usage__total_usage {app_container_metrics['precpu_stats']['cpu_usage']['total_usage']}
                    precpu_stats__precpu_stats__system_cpu_usage {app_container_metrics['precpu_stats']['system_cpu_usage']}
                    precpu_stats__precpu_stats__online_cpus {app_container_metrics['precpu_stats']['online_cpus']}'''
                                                            )
                return web.Response(text=prometheus_format_metrics)

    app = web.Application()
    app.add_routes([
        web.get('/__metrics', handle_metrics),
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()


def main():
    port = int(os.environ['PORT'])
    url = os.environ['ECS_CONTAINER_METADATA_URI'] + '/task/stats'

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    loop = asyncio.get_event_loop()
    loop.create_task(async_main(logger, port, url))
    loop.run_forever()


if __name__ == '__main__':
    main()
