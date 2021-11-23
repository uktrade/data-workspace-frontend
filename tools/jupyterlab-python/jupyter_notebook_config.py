import sys
import logging
import sentry_sdk
import sentry_sdk.transport
from sentry_sdk.integrations.tornado import TornadoIntegration


def _get_pool_options(_, __):
    # We use self-signed certs in the proxy
    return {"num_pools": 2, "cert_reqs": "CERT_NONE"}


sentry_sdk.transport.HttpTransport._get_pool_options = _get_pool_options
sentry_sdk.init()
sentry_sdk.init(integrations=[TornadoIntegration()])


handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)

loggers = [
    logging.getLogger(),
    logging.getLogger("urllib3"),
    logging.getLogger("tornado"),
    logging.getLogger("tornado.access"),
    logging.getLogger("tornado.application"),
    logging.getLogger("tornado.general"),
]
for logger in loggers:
    logger.addHandler(handler)
c = get_config()  # pylint: disable=undefined-variable # noqa

c.NotebookApp.ip = "0.0.0.0"
c.NotebookApp.log_level = "DEBUG"
c.NotebookApp.terminado_settings = {"shell_command": ["bash"]}
