#!/bin/sh

set -e

(
    cd "$(dirname "$0")"
    django-admin collectstatic --noinput

    # Not suitable on a cluster of size > 1, but for our purposes,
    # no need for more
    django-admin migrate

    # nginx is configured to log to stdout/stderr, _except_ before
    # it manages to read its config file. To avoid errors on startup,
    # we configure its prefix to be a writable location
    mkdir -p /home/django/logs

    # Start nginx, proxy and application
    echo "Starting nginx, proxy and gunicorn application..."
    nginx -p /home/django &
    PROXY_PORT='8001' UPSTREAM_ROOT='http://localhost:8002' python3 -m proxy &
    gunicorn app.wsgi:application -c gunicorn_config.py
)
