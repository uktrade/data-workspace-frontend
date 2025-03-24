import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from dataworkspace.apps.core.utils import (
    db_role_schema_suffix_for_user,
    new_private_database_credentials,
    postgres_user,
    source_tables_for_user,
    write_credentials_to_bucket,
)


class Command(BaseCommand):
    help = "Creates and saves DB credentials for all SSO users"

    def handle(self, *args, **options):
        self.stdout.write("store_db_creds_in_s3 started")

        bucket = settings.NOTEBOOKS_BUCKET
        self.stdout.write("Will store credentials in bucket {}".format(bucket))

        all_users = get_user_model().objects.order_by("last_name", "first_name", "id")
        for user in all_users:
            self.stdout.write(f"Creating credentials for {user.email}")

            source_tables_user_non_common, source_tables_user_common = source_tables_for_user(user)

            db_role_schema_suffix = db_role_schema_suffix_for_user(user)
            creds = new_private_database_credentials(
                db_role_schema_suffix,
                source_tables_user_non_common,
                source_tables_user_common,
                postgres_user(user.email),
                user,
                valid_for=datetime.timedelta(days=31),
            )
            write_credentials_to_bucket(user, creds)
            self.stdout.write(str(creds))

        self.stdout.write(self.style.SUCCESS("store_db_creds_in_s3 finished"))
