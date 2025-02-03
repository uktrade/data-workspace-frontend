# Monkey-patching should happen as early as possible ...
# pylint: disable=multiple-statements,wrong-import-position,wrong-import-order

# fmt: off
from gevent import monkey; monkey.patch_all()  # noqa: E402,E702
from psycogreen.gevent import patch_psycopg; patch_psycopg()  # noqa: E402,E702
from elasticapm.instrumentation.control import instrument; instrument()  # noqa: E402,E702
# fmt: on

# ... and then start the server proper

import signal

import gevent
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.utils.autoreload import run_with_reloader
from gevent.pywsgi import WSGIServer


def run_server():
    server = WSGIServer(("127.0.0.1", 8002), get_wsgi_application())
    gevent.signal_handler(signal.SIGTERM, server.stop)

    print("Starting WSGIServer...", flush=True)
    server.serve_forever()

    print("Stopping WSGIServer. Waiting for all requests to complete...", flush=True)
    gevent.get_hub().join()

    print("Requests completed. Exiting gracefully.", flush=True)


if settings.DEBUG is True and settings.LOCAL is True:
    print("Running in DEBUG mode with hot reloader")
    run_with_reloader(run_server)
else:
    run_server()
