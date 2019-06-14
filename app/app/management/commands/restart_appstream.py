from django.conf import (
    settings,
)
from django.core.management.base import (
    BaseCommand,
)

from app.appstream import (
    restart_fleet,
)

class Command(BaseCommand):

    def handle(self, *args, **options):
        print('Restarting fleet')
        restart_fleet()
