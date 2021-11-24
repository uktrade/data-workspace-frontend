from psycopg2 import connect

from django.conf import settings
from django.core.management.base import BaseCommand

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import database_dsn


class Command(BaseCommand):
    """Ensures that the databases are configured.

    Specifically, revoking the default public schema permissions that allows
    tables to be created
    """

    help = "Ensures the databases are configured"

    def handle(self, *args, **options):
        self.stdout.write("ensure_database_configured...")

        for database_name, database_data in settings.DATABASES_DATA.items():
            self.stdout.write(f"ensure_database_configured ensuring {database_name} is in db")
            Database.objects.get_or_create(memorable_name=database_name)

            self.stdout.write(
                f"ensure_database_configured {database_name} revoking public access..."
            )
            with connect(database_dsn(database_data)) as conn, conn.cursor() as cur:
                cur.execute("REVOKE ALL ON schema public FROM public;")
            self.stdout.write(
                f"ensure_database_configured {database_name} revoking public access... (done)"
            )

        self.stdout.write(self.style.SUCCESS("ensure_database_configured... (done)"))
