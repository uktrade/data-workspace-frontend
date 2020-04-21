#!/bin/bash

set -e

superset db upgrade
superset fab create-admin --username admin --firstname Admin --lastname User --email admin@dataworkspace.test --password admin
superset init

gunicorn \
	-w 10 \
	-k gevent \
	-b 0.0.0.0:8888 \
	--timeout 120 \
	--limit-request-line 0 \
	--limit-request-field_size 0 \
	'superset.app:create_app()'
