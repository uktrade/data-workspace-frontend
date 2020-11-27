#!/bin/sh

set -e

openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=analysis-workspace-postgres \
    -keyout ssl.key \
    -out ssl.crt && \
chown postgres:postgres ssl.key ssl.crt
chmod 0600 ssl.key ssl.crt

export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

docker-entrypoint.sh "$@" \
    -c shared_preload_libraries=pgaudit \
    -c log_destination=csvlog \
    -c logging_collector=on \
    -c ssl=on \
    -c ssl_cert_file=/ssl.crt \
    -c ssl_key_file=/ssl.key
