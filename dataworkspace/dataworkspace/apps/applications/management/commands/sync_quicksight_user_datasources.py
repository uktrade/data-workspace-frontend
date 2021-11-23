from django.core.management.base import BaseCommand
from django.conf import settings

from dataworkspace.apps.applications.utils import sync_quicksight_permissions


class Command(BaseCommand):
    """Sync master datasets and user permissions from Data Workspace to AWS QuickSight."""

    help = "Sync master datasets and user permissions from Data Workspace to AWS QuickSight."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        sync_quicksight_permissions()


if __name__ == "__main__":
    settings.configure()
    Command().handle()
