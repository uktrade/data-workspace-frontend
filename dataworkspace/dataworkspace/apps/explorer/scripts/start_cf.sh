#!/bin/bash

source ./dataworkspace/dataworkspace/apps/explorer/scripts/functions.sh

if [[ -z "${VCAP_SERVICES}" ]]
then
    :
else
    export REDIS_URL=$(echo $VCAP_SERVICES | jq -r '.redis[0].credentials.uri')
fi

run "./scripts/compile_assets.sh"
run "./scripts/compile_sass.sh"

run "python manage.py migrate --noinput"

run "waitress-serve --port=$PORT explorer.wsgi:application"
