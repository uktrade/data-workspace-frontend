import uuid
import datetime
import random

from django.contrib.auth import get_user_model
from django.utils.text import slugify
from faker import Faker  # noqa

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from dataworkspace.apps.datasets.models import (
    MasterDataset,
    VisualisationCatalogueItem,
    VisualisationLink,
    ReferenceDataset,
    Tag,
)


class TestData:
    def __init__(self):
        self.fake = Faker("en-GB")

    def get_dataset_name(self):
        return self.fake.company()

    def get_licence_text(self):
        return "Open Data"

    def get_licence_url(self):
        return self.fake.uri()

    def get_personal_data_text(self):
        return "Does not contain personal data"

    def get_no_restrictions_on_usage_text(self):
        return "No restrictions on usage"

    def get_restrictions_on_usage_text(self):
        return "Entered text must be either OFFICIAL or OFFICIAL-SENSITIVE."

    def get_is_draft(self):
        return bool(random.randint(0, 1))

    def get_no_retention_policy_text(self):
        return "No retention policy"

    def get_new_user(self):
        model = get_user_model()

        email = self.fake.ascii_safe_email()
        user = model.objects.create(
            username=email,
            is_staff=False,
            is_superuser=False,
            email=email,
            first_name=self.fake.first_name(),
            last_name=self.fake.last_name(),
        )

        return user

    def get_user(self):
        model = get_user_model()

        user = model.objects.all()

        if user.count():
            return user[0]

        return None


def get_random_tag(tag_type: TagType):
    tags = Tag.objects.filter(type=tag_type)

    if not tags.exists():
        return None

    offset = random.randint(0, tags.count() - 1)

    return tags[offset]


def create_fake_dataset(dataset_type=DataSetType.MASTER):
    if dataset_type not in [DataSetType.MASTER, DataSetType.DATACUT]:
        raise Exception(f"Can't handle a DatasetType of {dataset_type.name}")

    fake = Faker("en-GB")
    test_data = TestData()

    name = test_data.get_dataset_name()
    user = test_data.get_new_user()

    catalogue_item = MasterDataset.objects.create(
        name=name,
        type=dataset_type,
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
        user_access_type="REQUIRES_AUTHORIZATION",
        published=True,
    )

    return catalogue_item


def create_fake_visualisation_dataset():
    fake = Faker("en-GB")
    test_data = TestData()

    name = test_data.get_dataset_name()
    user = test_data.get_new_user()

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
        user_access_type="REQUIRES_AUTHORIZATION",
        published=True,
    )

    VisualisationLink.objects.create(
        visualisation_type="QUICKSIGHT",
        name=name,
        identifier=str(uuid.uuid4().hex),
        visualisation_catalogue_item=catalogue_item,
    )

    return catalogue_item


def create_fake_reference_dataset():
    fake = Faker("en-GB")
    test_data = TestData()

    name = test_data.get_dataset_name()
    user = test_data.get_new_user()

    table_name = (
        "ref_" + fake.first_name().lower() + datetime.datetime.now().strftime("%Y%m%d%H%M%s")
    )

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
        is_draft=test_data.get_is_draft(),
        published=True,
    )

    return catalogue_item
