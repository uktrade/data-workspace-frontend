#!/bin/sh

set -e

(
    cd "$(dirname "$0")"

    echo "starting celery..."
    celery worker --app dataworkspace.cel.celery_app --pool gevent --concurrency 150
)
