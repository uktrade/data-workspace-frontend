#!/bin/bash

set -e

superset db upgrade

# Creates or updates roles
superset init

gunicorn \
    -w 10 \
    -k gevent \
    -b 0.0.0.0:8000 \
    --timeout 120 \
    --limit-request-line 0 \
    --limit-request-field_size 0 \
    --reload \
    'superset.app:create_app()'
