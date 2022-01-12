#!/bin/sh

set -e

(
    cd "$(dirname "$0")"

    echo "starting celery..."
    nodemon -e py --watch dataworkspace -x celery --app dataworkspace.cel.celery_app worker --pool gevent --concurrency 150
)
