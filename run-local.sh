#!/bin/bash

(
    docker-compose -f docker-compose-dev.yml -p data-workspace up -d data-workspace-postgres data-workspace-redis

    set -e
    set -o allexport

    source .envs/local-dev.env

    cd dataworkspace

    django-admin migrate
    django-admin ensure_databases_configured
    django-admin ensure_application_template_models

    echo "Starting proxy and django dev server"
    PROXY_PORT=8000 UPSTREAM_ROOT=http://localhost:8002 python3 -m proxy &
    PROXY_PID=$!
    echo "Proxy PID: ${PROXY_PID}"
    trap "kill ${PROXY_PID}" EXIT INT TERM

    django-admin runserver 8002
)
