#!/bin/bash

set -e

celery --broker="${REDIS_URL}" flower --broker_api="${REDIS_URL}" --basic_auth=${FLOWER_USERNAME}:${FLOWER_PASSWORD} --port=80