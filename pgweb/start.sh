#!/bin/sh

set -e

export DATABASE_URL=$(python3 pgweb-config.py)

/usr/bin/pgweb --bind=0.0.0.0 --listen=8888
