#!/bin/sh

chown -R pgadmin:pgadmin /home/jovyan

set -e

sudo -E -H -u pgadmin /entrypoint.sh

