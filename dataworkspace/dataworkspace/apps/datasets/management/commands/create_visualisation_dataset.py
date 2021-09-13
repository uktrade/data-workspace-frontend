import uuid

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from faker import Faker  # noqa

from dataworkspace.apps.datasets.models import (
    VisualisationCatalogueItem,
    VisualisationLink,
)

fake = Faker("en-GB")


class Command(BaseCommand):
    help = "Creates one or more visualisation datasets. Will use fake values and create users if needed"

    def _get_license_text(self):
        return "Open Data"

    def _get_personal_data_text(self):
        return "Does not contain personal data"

    def _get_restrictions_on_usage_text(self):
        return "Entered text must be either OFFICIAL or OFFICIAL-SENSITIVE."

    def _get_user(self):
        model = get_user_model()

        user = model.objects.all()

        if user.count():
            return user[0]

        return None

    def handle(self, *args, **options):
        name = fake.company()
        user = self._get_user()

        self.stdout.write(f"creating new visualisation dataset {name}")

        catalogue_item = VisualisationCatalogueItem.objects.create(
            name=name,
            slug=slugify(name),
            short_description=fake.sentence(nb_words=20),
            description="<br>".join(fake.paragraphs(nb=3)),
            enquiries_contact=user,
            # perhaps add other users?
            licence=self._get_license_text(),
            personal_data=self._get_personal_data_text(),
            restrictions_on_usage=self._get_restrictions_on_usage_text(),
            user_access_type="REQUIRES_AUTHORIZATION",
            published=True,
        )

        VisualisationLink.objects.create(
            visualisation_type="QUICKSIGHT",
            name=name,
            identifier=str(uuid.uuid4().hex),
            visualisation_catalogue_item=catalogue_item,
        )

        self.stdout.write(
            self.style.SUCCESS(f"created new visualisation dataset {name} (done)")
        )
