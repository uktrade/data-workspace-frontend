from asyncio import create_task
import asyncio
import logging
import os
import re
import signal
import sys

from aiodnsresolver import DnsError, Resolver, IPv4AddressExpiresAt, TYPES
from dnsrewriteproxy import DnsProxy


async def async_main():
    public_zone = re.escape(os.environ["AWS_ROUTE53_ZONE"])
    private_zone = "jupyterhub"
    nameserver = os.environ["DNS_SERVER"]

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    logger = logging.getLogger("dnsrewriteproxy")
    logger.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)

    hosts = {
        # ECS seem to make these DNS queries. A query for localhost is
        # particularly odd, since it would typically be hard coded in
        # /etc/hosts
        b"localhost": {TYPES.A: IPv4AddressExpiresAt("127.0.0.1", expires_at=0)},
        b"1.amazon.pool.ntp.org": {TYPES.A: IPv4AddressExpiresAt("169.254.169.123", expires_at=0)},
        b"2.amazon.pool.ntp.org": {TYPES.A: IPv4AddressExpiresAt("169.254.169.123", expires_at=0)},
        b"3.amazon.pool.ntp.org": {TYPES.A: IPv4AddressExpiresAt("169.254.169.123", expires_at=0)},
    }

    def get_resolver():
        async def get_nameservers(_, __):
            for _ in range(0, 5):
                yield (1.0, (nameserver, 53))

        async def get_host(_, fqdn, qtype):
            try:
                return hosts[qtype][fqdn]
            except KeyError:
                return None

        return Resolver(get_nameservers=get_nameservers, get_host=get_host)

    start = DnsProxy(
        rules=(
            # The arango host in the public zone will already correctly
            # resolve to the private IP, so we pass that through
            (r"^(arango\." + public_zone + ")$", r"\1"),
            # ... other public zone hosts should resolve to the IP of the
            # private zone, e.g. gitlab
            (r"^(.+)\." + public_zone + "$", r"\1." + private_zone),
            # ... And amazon domains should remain as they are, e.g. S3, CloudWatch
            (r"(.+\.amazonaws\.com)$", r"\1"),
            (r"^(localhost)$", r"\1"),
            (r"^(1\.amazon\.pool\.ntp\.org)$", r"\1"),
            (r"^(2\.amazon\.pool\.ntp\.org)$", r"\1"),
            (r"^(3\.amazon\.pool\.ntp\.org)$", r"\1"),
        ),
        get_resolver=get_resolver,
    )
    logger.info("DNS server starting")
    proxy_task = await start()
    logger.info("DNS server started")

    async def handle_client(reader, writer):
        async def get_nameservers(_, __):
            yield (1.0, ("127.0.0.1", 53))

        await reader.read(100)
        resolve, _ = Resolver(get_nameservers=get_nameservers)

        try:
            await resolve("s3.eu-west-2.amazonaws.com", TYPES.A)
        except DnsError:
            status = "503 Service Unavailable"
        else:
            status = "200 OK"

        writer.write(b"HTTP/1.1 %b \r\ncontent-length: 0\r\n\r\n" % status.encode("utf8"))
        await writer.drain()
        writer.close()

    healthcheck_task = await create_task(asyncio.start_server(handle_client, "0.0.0.0", 8888))
    logger.info("[Healthcheck] server started")

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, proxy_task.cancel)
    loop.add_signal_handler(signal.SIGTERM, proxy_task.cancel)

    try:
        await proxy_task
        await healthcheck_task
    except asyncio.CancelledError:
        pass


asyncio.run(async_main())
print("DNS server exiting")
