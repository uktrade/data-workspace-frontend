from django.core.management.base import BaseCommand
from dataworkspace.apps.datasets.models import (
    MasterDataset,
    DataCutDataset,
    ReferenceDataset,
    VisualisationCatalogueItem,
)


class Command(BaseCommand):
    def handle(self, *args, **options):
        for ds in MasterDataset.objects.all():
            ds.save()

        for ds in DataCutDataset.objects.all():
            ds.save()

        for ds in ReferenceDataset.objects.all():
            ds.save()

        for ds in VisualisationCatalogueItem.objects.all():
            ds.save()
