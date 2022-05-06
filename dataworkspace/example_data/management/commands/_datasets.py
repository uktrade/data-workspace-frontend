from django.utils.text import slugify

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import MasterDataset, SourceTable

from ._tags import get_dev_source_tag, get_example_topic_tag, get_superset_tag

master_datasets = [
    {
        "name": "Trivial Example",
        "short_description": "A trivial dataset based on the DIT readme example",
        "description": '<div>A trivially simple dataset based on the example airflow DAG from DIT <a href="#">developer manual</a></div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>',
        "source_tables": [{"database": "datasets", "schema": "example", "table": "local__spoons"}],
    },
    {
        "name": "Superset Video Game Sales",
        "is_superset": True,
        "short_description": "A dataset of video game sales",
        "description": "A dataset of video game sales taken from superset example data",
        "source_tables": [
            {
                "database": "datasets",
                "schema": "example",
                "table": "superset__video_game_sales",
            },
        ],
    },
    {
        "name": "Superset Sales Data",
        "is_superset": True,
        "short_description": "A dataset of sales data",
        "description": "A dataset of sales data taken from superset example data",
        "source_tables": [
            {"database": "datasets", "schema": "example", "table": "superset__sales"}
        ],
    },
    {
        "name": "Superset Unicode Test",
        "is_superset": True,
        "short_description": "A dataset of unicode test data",
        "description": "A dataset of unicode test data taken from superset example data",
        "source_tables": [
            {"database": "datasets", "schema": "example", "table": "superset__unicode_test"}
        ],
    },
    {
        "name": "Superset Flights Test",
        "is_superset": True,
        "short_description": "A dataset of unicode test data",
        "description": "A dataset of unicode test data taken from superset example data",
        "source_tables": [
            {"database": "datasets", "schema": "example", "table": "superset__unicode_test"}
        ],
    },
]


def create_example_datasets(iam_user, iao_user, stdout):

    for dataset in master_datasets:

        catalogue_item, created = MasterDataset.objects.get_or_create(
            name=dataset["name"],
            defaults={
                "type": DataSetType.MASTER,
                "slug": slugify(dataset["name"]),
                "user_access_type": "REQUIRES_AUTHORIZATION",
                "published": True,
            },
        )

        stdout.write(
            "MasterDataset %s was %s" % (dataset["name"], "created" if created else "updated")
        )

        catalogue_item.information_asset_manager = iam_user
        catalogue_item.information_asset_owner = iao_user
        catalogue_item.short_description = dataset["short_description"]
        catalogue_item.description = dataset["description"]
        catalogue_item.tags.add(get_dev_source_tag())
        catalogue_item.tags.add(get_example_topic_tag())

        if dataset.get("is_superset"):
            catalogue_item.tags.add(get_superset_tag())

        catalogue_item.save()

        for source in dataset["source_tables"]:

            database = Database.objects.get(memorable_name=source["database"])

            table, created = SourceTable.objects.get_or_create(
                database=database,
                schema=source["schema"],
                table=source["table"],
                dataset=catalogue_item,
                defaults={"name": dataset["name"]},
            )

            stdout.write(
                "%s SourceTable %s was %s"
                % (catalogue_item.name, table.name, "created" if created else "updated")
            )
