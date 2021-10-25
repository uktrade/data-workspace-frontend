from django.core.management.base import BaseCommand
from dataworkspace.apps.datasets.models import (
    MasterDataset,
    DataCutDataset,
    ReferenceDataset,
    VisualisationCatalogueItem,
)


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Building tsvector for all existing datasets")

        masterds_count = MasterDataset.objects.all().count()
        for ds in MasterDataset.objects.all():
            ds.save()
        self.stdout.write(f"tsvector built for {masterds_count} master datasets")

        datacutds_count = MasterDataset.objects.all().count()
        for ds in DataCutDataset.objects.all():
            ds.save()
        self.stdout.write(f"tsvector built for {datacutds_count} data cut datasets")

        referenceds_count = MasterDataset.objects.all().count()
        for ds in ReferenceDataset.objects.all():
            ds.save()
        self.stdout.write(f"tsvector built for {referenceds_count} reference datasets")

        vis_count = MasterDataset.objects.all().count()
        for ds in VisualisationCatalogueItem.objects.all():
            ds.save()
        self.stdout.write(f"tsvector built for {vis_count} visualisations")

        self.stdout.write("done")
