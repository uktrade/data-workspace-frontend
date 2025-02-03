import psycopg2.sql
from django.conf import settings
from django.core.management.base import BaseCommand
from psycopg2 import connect

from dataworkspace.apps.core.utils import database_dsn


class Command(BaseCommand):
    """Deletes temporary Data Explorer results

    To be used from tests to cleanup between them
    """

    help = "Delete temporary Data Explorer result tables"

    def handle(self, *args, **options):
        self.stdout.write("deleting temporary Data Explorer result tables...")

        for _database_name, database_data in settings.DATABASES_DATA.items():
            with connect(database_dsn(database_data)) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_name
                    LIKE '%_tmp_query_%'
                """
                )
                for table_schema, table_name in cur.fetchall():
                    cur.execute(
                        psycopg2.sql.SQL("DROP TABLE {}.{}").format(
                            psycopg2.sql.Identifier(table_schema),
                            psycopg2.sql.Identifier(table_name),
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS("deleting temporary Data Explorer result tables (done)")
        )
