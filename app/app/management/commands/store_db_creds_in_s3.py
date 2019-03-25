from django.core.management.base import (
    BaseCommand,
)


class Command(BaseCommand):
    help = 'Creates and saves DB credentials for all SSO users'

    def handle(self, *args, **options):
        self.stdout.write('store_db_creds_in_s3 started')
        self.stdout.write(self.style.SUCCESS('store_db_creds_in_s3 finished'))
