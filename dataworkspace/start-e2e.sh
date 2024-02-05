#!/bin/sh
#TODO - can this be merged with start-dev.sh
set -e

(
    cd "$(dirname "$0")"

    django-admin collectstatic --noinput -i node_modules -i react_apps

    # Not suitable on a cluster of size > 1, but for our purposes,
    # no need for more
    django-admin migrate

    django-admin ensure_databases_configured
    django-admin ensure_application_template_models

    django-admin loaddata --ignorenonexistent --verbosity=2 \
      users \
      profiles \
      database \
      datasets \
      datasets_sourcelink \
      datasets_sourcetable \
      datasets_sourcetablefielddefinition \
      datasets_sourceview \
      datasets_bookmark \
      data_collections \
      eventlog


    django-admin waffle_flag HOME_PAGE_FLAG --everyone --create
    django-admin waffle_flag ACCESSIBLE_AUTOCOMPLETE_FLAG --everyone --create

    # nginx is configured to log to stdout/stderr, _except_ before
    # it manages to read its config file. To avoid errors on startup,
    # we configure its prefix to be a writable location
    mkdir -p /home/django/logs

    # Start nginx, proxy and application
    echo "Starting celery beat, nginx, proxy and django application..."
    parallel --will-cite --line-buffer --jobs 4 --halt now,done=1 ::: \
        "celery --app dataworkspace.cel.celery_app beat --pidfile= -S redbeat.RedBeatScheduler" \
        "python3 -m start" \
        "PROXY_PORT='8001' UPSTREAM_ROOT='http://localhost:8002' nodemon --watch proxy.py --exec 'python3 -m proxy'" \
        "nginx -p /home/django"
)
