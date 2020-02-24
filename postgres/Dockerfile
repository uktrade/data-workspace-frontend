FROM postgres:10.4

COPY /entrypoint.sh /
COPY /init-databases.sql /docker-entrypoint-initdb.d/

ENTRYPOINT /entrypoint.sh
