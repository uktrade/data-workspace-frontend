#!/bin/bash

set -e

mkdir -p /etc/rstudio/connections

while IFS='=' read -r name value ; do
  if [[ $name == *'DATABASE_DSN__'* ]]; then
    # Make available as environment variable
    echo "${name}='${!name}'" >> /home/rstudio/.Renviron

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

echo "S3_PREFIX='${S3_PREFIX}'" >> /home/rstudio/.Renviron
echo "AWS_DEFAULT_REGION='${AWS_DEFAULT_REGION}'" >> /home/rstudio/.Renviron
echo "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI='${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}'" >> /home/rstudio/.Renviron
/usr/lib/rstudio-server/bin/rserver
