#!/bin/sh

set -e

(
    cd "$(dirname "$0")"
    django-admin collectstatic

    # Not suitable on a cluster of size > 1, but for our purposes,
    # no need for more
    django-admin migrate

    # nginx is configured to log to stdout/stderr, _except_ before
    # it manages to read its config file. To avoid errors on startup,
    # we configure its prefix to be a writable location
    mkdir /home/django/logs

    # Start nginx, proxy and application
    nginx -p /home/django &
    PORT='8001' UPSTREAM_ROOT='http://127.0.0.1:8002' python3 -m proxy &
    gunicorn app.wsgi:application -c gunicorn_config.py
)
