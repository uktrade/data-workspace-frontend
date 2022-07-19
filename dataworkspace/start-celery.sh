#!/bin/sh

set -e

(
    cd "$(dirname "$0")"

    echo "starting celery..."
    parallel --will-cite --line-buffer --jobs 3 --halt now,done=1 ::: \
        "celery --app dataworkspace.cel.celery_app worker --pool gevent --prefetch-multiplier=1 --concurrency 150 --hostname spawner@%h -Q applications.spawner.spawn" \
        "celery --app dataworkspace.cel.celery_app worker --pool gevent --prefetch-multiplier=1 --concurrency 150 --hostname explorer@%h -Q explorer.tasks" \
        "celery --app dataworkspace.cel.celery_app worker --pool gevent --prefetch-multiplier=1 --concurrency 150 --hostname default@%h -X applications.spawner.spawn,explorer.tasks"
)
