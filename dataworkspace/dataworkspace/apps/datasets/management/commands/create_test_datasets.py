import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    DataSet,
    SourceTable,
    DatasetReferenceCode,
)

from faker import Faker

fake = Faker()


class Command(BaseCommand):
    help = "Creates dataset entries corresponding to /postgres/2-init-databases.sql"

    def add_arguments(self, parser):
        parser.add_argument(
            "dataset_type",
            nargs="?",
            type=str,
            help="Type of dataset to create",
            default="MASTER",
        )

    @transaction.atomic()
    def handle(self, *args, **options):
        dataset_type = options["dataset_type"]

        reference_code, _ = DatasetReferenceCode.objects.get_or_create(code="TEST")
        dataset_name = fake.company()

        dataset = DataSet.objects.create(
            name=dataset_name,
            description=fake.paragraph(),
            short_description=fake.sentence(),
            slug=slugify(dataset_name),
            id=str(uuid.uuid4()),
            published=True,
            reference_code=reference_code,
            type=DataSetType[dataset_type].value,
        )

        # Requires a value in .env for DATA_DB__my_database__NAME=datasets
        database, _ = Database.objects.get_or_create(memorable_name="my_database")
        table_name = fake.catch_phrase()

        SourceTable.objects.create(
            id=uuid.uuid4(),
            dataset=dataset,
            database=database,
            schema="public",
            table="test_dataset",
            name=fake.catch_phrase(),
        )

        self.stdout.write(f"Created master dataset '{dataset_name}' -> {database.memorable_name}.public.test_dataset")