import logging

import psycopg2
from django.conf import settings
from psycopg2 import sql

from dataworkspace.apps.core.utils import database_dsn

logger = logging.getLogger('app')


def get_columns(database_name, schema=None, table=None, query=None):
    if table is not None and schema is not None:
        source = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    elif query is not None:
        source = sql.SQL("({}) AS custom_query".format(query.rstrip(";")))
    else:
        raise ValueError("Either table or query are required")

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[database_name])
    ) as connection:
        try:
            return query_columns(connection, source)
        except Exception:
            logger.error("Failed to get dataset fields", exc_info=True)
            return []


def query_columns(connection, source):
    sql = psycopg2.sql.SQL('SELECT * from {} WHERE false').format(source)
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [c[0] for c in cursor.description]
