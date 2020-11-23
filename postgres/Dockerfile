FROM postgres:10.4

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-10-pgaudit

COPY /entrypoint.sh /
COPY /init-databases.sql /docker-entrypoint-initdb.d/

ENTRYPOINT /entrypoint.sh
