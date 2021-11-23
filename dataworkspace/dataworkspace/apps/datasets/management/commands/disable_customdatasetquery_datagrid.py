from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.models import CustomDatasetQuery


class Command(BaseCommand):
    help = "Enables ag-grid for CustomDatasetQuery"

    def handle(self, *args, **options):
        self.stdout.write("enabling ag-grid for DataCut datasets ...")

        CustomDatasetQuery.objects.all().update(data_grid_enabled=False)

        self.stdout.write(self.style.SUCCESS("enabling ag-grid for CustomDatasetQuery (done)"))
