#!/bin/bash

source ./dataworkspace/dataworkspace/apps/explorer/scripts/functions.sh

if [[ -z "${DEVELOPMENT_SERVER}" ]]
then
    export PORT=8000
fi

if [ -z "${POSTGRES_DB}" ] && [ -z "${POSTGRES_PORT}" ] \
    && [ -z "${POSTGRES_HOST}" ] && [ -z "${POSTGRES_PASSWORD}" ] \
    && [ -z "${POSTGRES_USER}" ]
then
    db_config=$(python3 scripts/data-explorer-config.py)
    if [ "$db_config" == "DATABASE_DSN not set" ];
    then
        echo $db_config
    else
        echo 'data workspace db config found'
        IFS=', ' read -r -a array <<< "$db_config"
        export POSTGRES_DB=${array[4]}
        export POSTGRES_PORT=${array[3]}
        export POSTGRES_HOST=${array[2]}
        export POSTGRES_PASSWORD=${array[1]}
        export POSTGRES_USER=${array[0]}
        export AUTO_LOGIN=True
        export PORT=8888
    fi
fi

if [ -z "${COMPILE_ASSETS}" ];
then
    :
else
    run "npm install"
    run "./scripts/compile_assets.sh"
fi
run "./scripts/compile_sass.sh"
run "./scripts/start_server.sh"
