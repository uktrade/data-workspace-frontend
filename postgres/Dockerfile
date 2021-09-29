FROM postgres:10.4

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-10-pgaudit

COPY /entrypoint.sh /
COPY /1-init-libraries.sh /docker-entrypoint-initdb.d/
COPY /2-init-databases.sql /docker-entrypoint-initdb.d/
COPY /3-init-functions.sql /docker-entrypoint-initdb.d/

ENTRYPOINT /entrypoint.sh
