#!/bin/bash

set -e

mkdir -p /etc/rstudio/connections
python3 rstudio-db-creds.py
/usr/lib/rstudio-server/bin/rserver
