from django.conf import (
    settings,
)
from django.core.management.base import (
    BaseCommand,
)

from app.appstream import (
    scale_fleet,
    get_fleet_scale,
)

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--min-capacity', type=int)
        parser.add_argument('--max-capacity', type=int)

    def handle(self, *args, **options):

        min_capacity = options['min_capacity']
        max_capacity = options['max_capacity']

        print('Scaling fleet: Min = ' + str(min_capacity) + '  Max = ' + str(max_capacity))
        scale_fleet(min_capacity, max_capacity)

        get_fleet_scale()
