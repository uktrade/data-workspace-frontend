import sys

from dataworkspace.apps.core.models import Database
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from faker import Faker  # noqa

from dataworkspace.apps.datasets.models import MasterDataset, DataSetVisualisation
from dataworkspace.apps.example_data.management.commands._vega_utils import (
    get_fake_vega_definition,
)


class Command(BaseCommand):
    help = "Adds a fake vega visualisations to a master dataset"

    def add_arguments(self, parser):
        parser.add_argument(
            "id", type=str, help="Id for the master dataset",
        )

        parser.add_argument(
            "phase_name",
            type=str,
            nargs="?",
            default="",
            help="GDS phase name (optional)",
        )

    def handle(self, *args, **options):
        fake = Faker("en-GB")
        dataset_id = options["id"]
        phase_name = options["phase_name"]

        try:
            dataset = MasterDataset.objects.get(pk=dataset_id)
        except MasterDataset.DoesNotExist:
            self.stderr.write(f"No master dataset found with id {dataset_id}")
            sys.exit(1)
        except ValidationError:
            self.stderr.write(f"f{dataset_id} doesn't appear to be a valid dataset id")
            sys.exit(1)

        database = Database.objects.get(memorable_name="my_database")

        # very basic static vega definition
        name = fake.job()
        vis = DataSetVisualisation.objects.create(
            name=name,
            summary=fake.sentence(nb_words=20),
            database=database,
            dataset=dataset,
            vega_definition_json=get_fake_vega_definition(),
            gds_phase_name=phase_name,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Add {name} vega visualistaion to {dataset}")
        )
