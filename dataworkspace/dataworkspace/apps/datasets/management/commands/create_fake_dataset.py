import sys

from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from dataworkspace.apps.datasets.management.commands._create_utils import (
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
            "--topic",
            action="store_true",
            help="Assign the dataset to a random topic tag if any exist",
        )

        parser.add_argument(
            "-s",
            "--source",
            action="store_true",
            help="Assign the dataset to a random source tag if any exist",
        )

    def handle(self, *args, **options):
        dataset_type_text = options["type"].upper()

        if dataset_type_text not in DataSetType.__members__:
            self.stderr.write(self.style.ERROR(f"{options['type']} is not a valid DataSetType"))
            self.print_help("manage.py", "create_fake_dataset")
            sys.exit(1)

        should_add_topic = options["topic"]
        should_add_source = options["source"]

        if should_add_topic and should_add_source:
            self.stderr.write(self.style.ERROR("Please choose either --topic or --source tags"))
            self.print_help("manage.py", "create_fake_dataset")
            sys.exit(1)

        if should_add_topic:
            tag_type = TagType.TOPIC
        elif should_add_source:
            tag_type = TagType.SOURCE
        else:
            tag_type = None

        dataset_type = DataSetType[dataset_type_text]
        count = options["count"]

        for x in range(count):
            if dataset_type is DataSetType.VISUALISATION:
                catalogue_item = create_fake_visualisation_dataset()
            elif dataset_type is DataSetType.REFERENCE:
                catalogue_item = create_fake_reference_dataset()
            else:
                catalogue_item = create_fake_dataset(dataset_type=dataset_type)

            tag_msg = ""

            if tag_type:
                tag = get_random_tag(tag_type)
                catalogue_item.tags.add(tag)
                catalogue_item.save()
                tag_msg = f" using tag {tag.name}"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{x + 1:02}: created new {dataset_type.name} dataset {catalogue_item.name} {catalogue_item.id}{tag_msg}"
                )
            )
