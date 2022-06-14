from django.core.management.base import BaseCommand
from dataworkspace.apps.datasets.search import update_datasets_average_daily_users


class Command(BaseCommand):
    def handle(self, *args, **options):
        update_datasets_average_daily_users()
