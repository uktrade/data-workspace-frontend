from django.core.management.base import BaseCommand
from faker import Faker  # noqa

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.example_data.management.commands._create_utils import create_fake_dataset, \
    create_fake_visualisation_dataset, create_fake_reference_dataset


class Command(BaseCommand):
    help = "Creates a dataset. Will use fake values and create users if needed"

    def add_arguments(self, parser):
        parser.add_argument("type", type=str, help=f"Which type of dataset to create - [MASTER, REFERENCE, DATACUT]")

    def handle(self, *args, **options):

        dataset_type_text = options["type"]
        dataset_type = DataSetType[dataset_type_text]

        if dataset_type is DataSetType.VISUALISATION:
            dataset_name, dataset_id = create_fake_visualisation_dataset()
        elif dataset_type is DataSetType.REFERENCE:
            dataset_name, dataset_id = create_fake_reference_dataset()
        else:
            dataset_name, dataset_id = create_fake_dataset(dataset_type=dataset_type)

        self.stdout.write(
            self.style.SUCCESS(f"created new {dataset_type.name} dataset {dataset_name} {dataset_id}")
        )
