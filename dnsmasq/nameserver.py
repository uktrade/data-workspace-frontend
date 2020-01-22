import asyncio
import logging
import os
import re
import signal
import sys

from aiodnsresolver import Resolver
from dnsrewriteproxy import DnsProxy


async def async_main():
    public_zone = re.escape(os.environ['AWS_ROUTE53_ZONE'])
    private_zone = 'jupyterhub'
    nameserver = os.environ['DNS_SERVER']

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    logger = logging.getLogger('dnsrewriteproxy')
    logger.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)

    def get_resolver():
        async def get_nameservers(_, __):
            for _ in range(0, 5):
                yield (1.0, (nameserver, 53))

        return Resolver(get_nameservers=get_nameservers)

    start = DnsProxy(
        rules=(
            # The docker registry host in the public zone will already correctly
            # resolve to the private IP, so we pass that through
            (r'^(registry\.' + public_zone + ')$', r'\1'),
            # ... other public zone hosts should resolve to the IP of the
            # private zone, e.g. gitlab
            (r'^(.+)\.' + public_zone + '$', r'\1.' + private_zone),
            # ... And amazon domains should remain as they are, e.g. S3, CloudWatch
            (r'(.+\.amazonaws\.com)$', r'\1'),
        ),
        get_resolver=get_resolver,
    )
    logger.info('DNS server starting')
    proxy_task = await start()
    logger.info('DNS server started')

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, proxy_task.cancel)
    loop.add_signal_handler(signal.SIGTERM, proxy_task.cancel)

    try:
        await proxy_task
    except asyncio.CancelledError:
        pass


asyncio.run(async_main())
print('DNS server exiting')
