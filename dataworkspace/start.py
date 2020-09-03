# Monkey-patching should happen as early as possible ...

# fmt: off
from gevent import monkey; monkey.patch_all()  # noqa: E402,E702
from psycogreen.gevent import patch_psycopg; patch_psycopg()  # noqa: E402,E702
# fmt: on

# ... and then start the server proper

import signal

from django.core.wsgi import get_wsgi_application
import gevent
from gevent.pywsgi import WSGIServer

server = WSGIServer(('127.0.0.1', 8002), get_wsgi_application())
gevent.signal_handler(signal.SIGTERM, server.stop)

print('Starting WSGIServer...', flush=True)
server.serve_forever()

print('Stopping WSGIServer. Waiting for all requests to complete...', flush=True)
gevent.get_hub().join()

print('Requests completed. Exiting gracefully.', flush=True)
