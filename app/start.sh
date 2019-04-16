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
    gunicorn app.wsgi:application -c gunicorn_config.py & nginx -p /home/django
)
