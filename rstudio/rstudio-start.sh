#!/bin/bash

set -e

mkdir -p /etc/rstudio/connections
python3 rstudio-db-creds.py

echo "S3_PREFIX='${S3_PREFIX}'" >> /home/rstudio/.Renviron
echo "AWS_DEFAULT_REGION='${AWS_DEFAULT_REGION}'" >> /home/rstudio/.Renviron
echo "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI='${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}'" >> /home/rstudio/.Renviron
/usr/lib/rstudio-server/bin/rserver
