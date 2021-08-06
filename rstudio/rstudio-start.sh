#!/bin/bash

mkdir -p /etc/rstudio/connections

# When on EFS, we expect to not be able to change ownership, and we don't need to
chown -R rstudio:rstudio /home/rstudio

set -e

# A previous version of this script wrote environment variables to this file,
# which was synced between container starts. Deleting to ensure we don't
# incorrectly use old values
rm -f /home/rstudio/.Renviron

while IFS='=' read -r name value ; do
  if [[ $name == *'DATABASE_DSN__'* ]]; then
    # Make available as environment variable
    echo "${name}='${!name}'" >> /etc/R/Renviron.site

    # Make available as connection in the UI
    conn_name=$(echo ${name}    | sed -E 's/DATABASE_DSN__(.*)/\1/')
    db_user=$(echo ${!name}     | sed -E 's/.*user=([a-z0-9_]+).*/\1/')
    db_password=$(echo ${!name} | sed -E 's/.*password=([a-zA-Z0-9_]+).*/\1/')
    db_port=$(echo ${!name}     | sed -E 's/.*port=([0-9]+).*/\1/')
    db_name=$(echo ${!name}     | sed -E 's/.*name=([a-z0-9_-]+).*/\1/')
    db_host=$(echo ${!name}     | sed -E 's/.*host=([a-z0-9_\.-]+).*/\1/')

    echo "library(DBI)" > "/etc/rstudio/connections/$conn_name.R"
    echo "con <- dbConnect(RPostgreSQL::PostgreSQL(), user='${db_user}', password='$db_password', host='$db_host', port='$db_port', dbname='$db_name')" >> "/etc/rstudio/connections/$conn_name.R"
  fi
done < <(env)

echo "APP_SCHEMA='${APP_SCHEMA}'" >> /etc/R/Renviron.site
echo "S3_PREFIX='${S3_PREFIX}'" >> /etc/R/Renviron.site
echo "AWS_DEFAULT_REGION='${AWS_DEFAULT_REGION}'" >> /etc/R/Renviron.site
echo "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI='${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}'" >> /etc/R/Renviron.site
echo "TZ='Europe/London'" >> /etc/R/Renviron.site

sudo -E -H -u rstudio /usr/lib/rstudio-server/bin/rserver
