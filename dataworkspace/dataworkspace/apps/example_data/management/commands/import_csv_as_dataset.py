import csv
from os import path

from django.core.management.base import BaseCommand
from faker import Faker  # noqa

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.example_data.management.commands._create_utils import create_fake_dataset


class Command(BaseCommand):
    help = "Creates a dataset and imports the CSV file for this dataset"

    def add_arguments(self, parser):
        parser.add_argument("input_file", type=str, help="path to a CSV file")
        parser.add_argument("--type", type=str, help=f"Which type of dataset to create - [MASTER, REFERENCE, DATACUT]. Defaults to MASTER", default="MASTER")

    def handle(self, *args, **options):

        dataset_type_text = options["type"]
        filename = options["input_file"]

        full_path = path.abspath(filename)

        self.stdout.write(full_path)
        self.stdout.write(dataset_type_text)

        with open(full_path, "r") as file:
            reader = csv.DictReader(file, delimiter=",")

            for row in reader:
                pass

            self.stdout.write(str(reader.fieldnames))

