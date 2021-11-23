import datetime

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker  # noqa

from dataworkspace.apps.datasets.management.commands._create_utils import TestData
from dataworkspace.apps.datasets.models import ReferenceDataset

fake = Faker("en-GB")


class Command(BaseCommand):
    help = "Creates a single reference dataset. Will use fake values and create users if needed"

    def handle(self, *args, **options):
        test_data = TestData()

        name = test_data.get_dataset_name()
        user = test_data.get_new_user()

        table_name = (
            "ref_" + fake.first_name().lower() + datetime.datetime.now().strftime('%Y%m%d%H%M%s')
        )

        self.stdout.write(f"creating new master dataset {name}")

        catalogue_item = ReferenceDataset.objects.create(
            name=name,
            table_name=table_name,
            slug=slugify(name),
            short_description=fake.sentence(nb_words=20),
            description="<br>".join(fake.paragraphs(nb=3)),
            enquiries_contact=user,
            licence=test_data.get_licence_text(),
            # licence_url=test_data.get_licence_url(),
            restrictions_on_usage=test_data.get_no_restrictions_on_usage_text(),
            published=True,
        )

        self.stdout.write(
            self.style.SUCCESS(f"created new master dataset {name} {catalogue_item.id}")
        )
