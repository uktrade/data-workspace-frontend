#!/bin/bash
# shared libraries are not picked up running sql via /docker-entrypoint-initdb.d/
# This script forces a reload to enable it manually before the test databases are created.

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    ALTER SYSTEM SET shared_preload_libraries='pgaudit';
EOSQL

pg_ctl restart
