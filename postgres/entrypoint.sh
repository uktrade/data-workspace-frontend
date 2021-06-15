#!/bin/sh

set -e

openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=analysis-workspace-postgres \
    -keyout ssl.key \
    -out ssl.crt && \
chown postgres:postgres ssl.key ssl.crt
chmod 0600 ssl.key ssl.crt

mkdir -p /var/log/postgres
chown postgres:postgres /var/log/postgres

export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

docker-entrypoint.sh "$@" \
    -c shared_preload_libraries=pgaudit \
    -c log_destination=csvlog \
    -c logging_collector=on \
    -c pgaudit.log=none \
    -c pgaudit.log_catalogue=off \
    -c ssl=on \
    -c ssl_cert_file=/ssl.crt \
    -c ssl_key_file=/ssl.key \
    -c log_directory=/var/log/postgres \
    -c log_file_mode=0644
