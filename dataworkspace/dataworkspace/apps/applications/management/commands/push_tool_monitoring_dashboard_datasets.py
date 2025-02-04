from django.conf import settings
from django.core.management.base import BaseCommand

from dataworkspace.apps.applications.utils import push_tool_monitoring_dashboard_datasets


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        push_tool_monitoring_dashboard_datasets()


if __name__ == "__main__":
    settings.configure()
    Command().handle()
