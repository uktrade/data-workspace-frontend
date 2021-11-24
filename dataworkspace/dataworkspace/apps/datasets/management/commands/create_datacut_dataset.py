from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker  # noqa

from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.datasets.management.commands._create_utils import TestData
from dataworkspace.apps.datasets.models import MasterDataset

fake = Faker("en-GB")


class Command(BaseCommand):
    help = "Creates a datacut dataset. Will use fake values and create users if needed"

    def handle(self, *args, **options):
        test_data = TestData()

        name = test_data.get_dataset_name()
        user = test_data.get_new_user()

        self.stdout.write(f"creating new datacut dataset {name}")

        catalogue_item = MasterDataset.objects.create(
            name=name,
            type=DataSetType.DATACUT,
            slug=slugify(name),
            short_description=fake.sentence(nb_words=20),
            description="<br>".join(fake.paragraphs(nb=3)),
            enquiries_contact=user,
            information_asset_owner=user,
            information_asset_manager=user,
            licence=test_data.get_licence_text(),
            licence_url=test_data.get_licence_url(),
            personal_data=test_data.get_personal_data_text(),
            restrictions_on_usage=test_data.get_no_restrictions_on_usage_text(),
            retention_policy=test_data.get_no_retention_policy_text(),
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            published=True,
        )

        self.stdout.write(
            self.style.SUCCESS(f"created new datacut dataset {name} {catalogue_item.id}")
        )
