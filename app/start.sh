#!/bin/sh

gunicorn app.wsgi:application -D -c gunicorn_config.py

RANDFILE="$HOME/openssl_rnd"
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=selfsigned \
	-keyout /home/django/ssl.key \
	-out /home/django/ssl.crt

# nginx is configured to log to stdout/stderr, _except_ before
# it manages to read its config file. To avoid errors on startup,
# we configure its prefix to be a writable location
mkdir /home/django/logs
nginx -p /home/django
