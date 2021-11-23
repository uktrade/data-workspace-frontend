import asyncio
import json
import logging
import os
import sys
import textwrap

import aiohttp
from aiohttp import web


async def async_main(logger, port, url):
    async def handle_metrics(_):
        async with aiohttp.ClientSession() as client_session:
            async with client_session.get(url) as response:
                task_metrics = json.loads(await response.text())
                logger.debug(task_metrics)
                app_container_metrics = [
                    container_metrics
                    for _, container_metrics in task_metrics.items()
                    # Fargate 1.3.0
                    if "-metrics-" not in container_metrics["name"]
                    and "-internalecspause-" not in container_metrics["name"]
                    and "-s3sync-" not in container_metrics["name"]
                    # Fargate 1.4.0
                    and container_metrics["name"] != "metrics"
                    and container_metrics["name"] != "s3sync"
                    and container_metrics["name"] != "aws-fargate-supervisor"
                ][0]

                # precpu_stats added and used in Fargate 1.3.0. However, these are empty in
                # Fargate 1.4.0, so moving over to cpu_stats
                prometheus_format_metrics = textwrap.dedent(
                    f"""\
                    memory_stats__usage {app_container_metrics['memory_stats']['usage']}
                    cpu_stats__cpu_usage__total_usage {app_container_metrics['cpu_stats']['cpu_usage']['total_usage']}
                    precpu_stats__cpu_usage__total_usage {app_container_metrics['cpu_stats']['cpu_usage']['total_usage']}"""
                )
                return web.Response(text=prometheus_format_metrics)

    app = web.Application()
    app.add_routes([web.get("/__metrics", handle_metrics)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


def main():
    port = int(os.environ["PORT"])
    url = os.environ["ECS_CONTAINER_METADATA_URI"] + "/task/stats"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    loop = asyncio.get_event_loop()
    loop.create_task(async_main(logger, port, url))
    loop.run_forever()


if __name__ == "__main__":
    main()
