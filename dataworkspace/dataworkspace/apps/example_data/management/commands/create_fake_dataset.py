import sys

from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.example_data.management.commands._create_utils import (
    create_fake_dataset,
    create_fake_visualisation_dataset,
    create_fake_reference_dataset,
    get_random_tag,
)


class Command(BaseCommand):
    help = "Creates a dataset. Will use fake values and create users if needed"

    def add_arguments(self, parser):
        parser.add_argument(
            "type",
            type=str,
            help="Which type of dataset to create - [MASTER, REFERENCE, DATACUT, VISUALISATION]",
        )

        parser.add_argument(
            "count",
            type=int,
            nargs="?",
            default=1,
            help="The number of datasets to create (default 1)",
        )

        parser.add_argument(
            "-t",
            "--tag",
            action="store_true",
            help="Assign the dataset to a random tag if any exist",
        )

    def handle(self, *args, **options):

        dataset_type_text = options["type"].upper()

        if dataset_type_text not in DataSetType.__members__:
            self.stderr.write(
                self.style.ERROR(f"{options['type']} is not a valid DataSetType")
            )
            self.print_help("manage.py", "create_fake_dataset")
            sys.exit(1)

        dataset_type = DataSetType[dataset_type_text]
        count = options["count"]
        should_add_tag = options["tag"]

        for x in range(count):
            if dataset_type is DataSetType.VISUALISATION:
                catalogue_item = create_fake_visualisation_dataset()
            elif dataset_type is DataSetType.REFERENCE:
                catalogue_item = create_fake_reference_dataset()
            else:
                catalogue_item = create_fake_dataset(dataset_type=dataset_type)

            if should_add_tag:
                tag = get_random_tag()
                catalogue_item.tags.add(tag)
                catalogue_item.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"{x+1:02}: created new {dataset_type.name} dataset {catalogue_item.name} {catalogue_item.id}"
                )
            )
