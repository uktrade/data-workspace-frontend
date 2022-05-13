#!/bin/sh

set -e

(
    cd "$(dirname "$0")"

    echo "starting celery..."
    celery --app dataworkspace.cel.celery_app worker --pool gevent --prefetch-multiplier=1 --concurrency 150 -Q explorer.tasks
)

