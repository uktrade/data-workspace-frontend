#!/bin/sh

set -e

(
    cd "$(dirname "$0")"

    echo "starting celery..."
    nodemon -e py --watch dataworkspace -x celery worker --app dataworkspace.cel.celery_app --pool gevent --concurrency 150
)
