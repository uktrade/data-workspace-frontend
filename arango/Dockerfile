FROM arangodb:3.11.6

COPY /1-init-db.sh /docker-entrypoint-initdb.d/
COPY /2-init-datasets.js /docker-entrypoint-initdb.d/
