#!/bin/sh

set -e

parallel --will-cite --line-buffer --jobs 2 --halt now,done=1 ::: \
    "python3 fetch_targets.py" \
    "/usr/local/bin/prometheus \
        --config.file=/etc/prometheus/prometheus.yml \
        --storage.tsdb.path=/prometheus \
        --web.console.libraries=/etc/prometheus/console_libraries \
        --web.console.templates=/etc/prometheus/consoles \
        --log.level=debug"
