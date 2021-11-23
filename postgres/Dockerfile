FROM postgres:12.9

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-12-pgaudit

COPY /entrypoint.sh /
COPY /1-init-libraries.sh /docker-entrypoint-initdb.d/
COPY /2-init-databases.sql /docker-entrypoint-initdb.d/

ENTRYPOINT /entrypoint.sh
