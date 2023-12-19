#!/bin/sh

set -e

export ARANGO_ROOT_PASSWORD=arango

/entrypoint.sh "$@"