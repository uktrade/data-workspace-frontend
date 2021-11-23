import uuid

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker  # noqa

from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.management.commands._create_utils import TestData
from dataworkspace.apps.datasets.models import (
    VisualisationCatalogueItem,
    VisualisationLink,
)

fake = Faker("en-GB")


class Command(BaseCommand):
    help = "Creates a visualisation dataset. Will use fake values and create users if needed"

    def handle(self, *args, **options):
        test_data = TestData()

        name = test_data.get_dataset_name()
        user = test_data.get_new_user()

        self.stdout.write(f"creating new visualisation dataset {name}")

        catalogue_item = VisualisationCatalogueItem.objects.create(
            name=name,
            slug=slugify(name),
            short_description=fake.sentence(nb_words=20),
            description="<br>".join(fake.paragraphs(nb=3)),
            enquiries_contact=user,
            information_asset_owner=user,
            information_asset_manager=user,
            licence=test_data.get_licence_text(),
            personal_data=test_data.get_personal_data_text(),
            restrictions_on_usage=test_data.get_restrictions_on_usage_text(),
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            published=True,
        )

        VisualisationLink.objects.create(
            visualisation_type="QUICKSIGHT",
            name=name,
            identifier=str(uuid.uuid4().hex),
            visualisation_catalogue_item=catalogue_item,
        )

        self.stdout.write(self.style.SUCCESS(f"created new visualisation dataset {name} (done)"))
