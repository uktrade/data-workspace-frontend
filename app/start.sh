#!/bin/sh

export KEYFILE="$HOME/ssl.key"
export CERTFILE="$HOME/ssl.crt"
RANDFILE="$HOME/openssl_rnd"
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=selfsigned \
	-keyout "$KEYFILE" \
	-out "$CERTFILE"

gunicorn app.wsgi:application -c gunicorn_config.py
