#!/bin/sh

openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=sentryproxy.jupyterhub \
    -keyout ssl.key \
    -out ssl.crt
chown nginx ssl.key ssl.crt
chmod 0600 ssl.key ssl.crt

exec tini -- "$@"
