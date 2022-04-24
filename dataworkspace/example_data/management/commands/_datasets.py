from dataworkspace.apps.datasets.models import MasterDataset
from dataworkspace.apps.datasets.constants import DataSetType, TagType

from ._tags import get_local_source_tag

from django.utils.text import slugify

master_datasets = [
    {
        "name": "Trivial Example",
        "short_description": "A trivial dataset based on the DIT readme example",
        "description": '<div>A trivially simple dataset based on the example airflow DAG from DIT <a href="#">developer manual</a></div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>',
    }
]


def create_example_datasets(iam_user, iao_user, stdout):

    for dataset in master_datasets:

        catalogue_item, created = MasterDataset.objects.get_or_create(
            name=dataset["name"],
            defaults={
                "type": DataSetType.MASTER,
                "slug": slugify(dataset["name"]),
                # short_description=fake.sentence(nb_words=20),
                # description="<br>".join(fake.paragraphs(nb=3)),
                # enquiries_contact=user,
                # information_asset_manager=user,
                # licence=test_data.get_licence_text(),
                # licence_url=test_data.get_licence_url(),
                # personal_data=test_data.get_personal_data_text(),
                # restrictions_on_usage=test_data.get_no_restrictions_on_usage_text(),
                # retention_policy=test_data.get_no_retention_policy_text(),
                "user_access_type": "REQUIRES_AUTHORIZATION",
                "published": True,
            },
        )

        stdout.write(
            "MasterDataset %s was %s"
            % (dataset["name"], "created" if created else "updated")
        )

        catalogue_item.information_asset_manager = iam_user
        catalogue_item.information_asset_owner = iao_user
        catalogue_item.short_description = dataset["short_description"]
        catalogue_item.description = dataset["description"]
        catalogue_item.tags.add(get_local_source_tag())
        catalogue_item.save()
