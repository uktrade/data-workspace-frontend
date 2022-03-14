import datetime
from unittest.mock import call, MagicMock, patch
import pytz

from django.conf import settings
from django.db import connections
from django.test import override_settings
from freezegun import freeze_time
import pytest

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    Notification,
    ReferenceDatasetField,
    UserNotification,
)
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    get_code_snippets_for_query,
    get_code_snippets_for_table,
    link_superset_visualisations_to_related_datasets,
    process_quicksight_dashboard_visualisations,
    send_notification_emails,
    store_custom_dataset_query_table_structures,
    store_reference_dataset_metadata,
)
from dataworkspace.datasets_db import get_custom_dataset_query_changelog
from dataworkspace.tests.factories import (
    CustomDatasetQueryFactory,
    DataSetFactory,
    ReferenceDatasetFactory,
    ReferenceDatasetFieldFactory,
    SourceTableFactory,
    VisualisationLinkFactory,
)


def test_dataset_type_to_manage_unpublished_permission_codename():
    assert (
        dataset_type_to_manage_unpublished_permission_codename(0)
        == "datasets.manage_unpublished_reference_datasets"
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSetType.DATACUT)
        == "datasets.manage_unpublished_datacut_datasets"
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSetType.MASTER)
        == "datasets.manage_unpublished_master_datasets"
    )


@pytest.mark.django_db
def test_get_code_snippets_for_table(metadata_db):
    ds = DataSetFactory.create(type=DataSetType.MASTER)
    sourcetable = SourceTableFactory.create(dataset=ds, schema="public", table="MY_LOVELY_TABLE")

    snippets = get_code_snippets_for_table(sourcetable)
    assert """SELECT * FROM \\"public\\".\\"MY_LOVELY_TABLE\\" LIMIT 50""" in snippets["python"]
    assert """SELECT * FROM \\"public\\".\\"MY_LOVELY_TABLE\\" LIMIT 50""" in snippets["r"]
    assert snippets["sql"] == """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50"""


def test_get_code_snippets_for_query(metadata_db):
    snippets = get_code_snippets_for_query("SELECT * FROM foo")
    assert "SELECT * FROM foo" in snippets["python"]
    assert "SELECT * FROM foo" in snippets["r"]
    assert snippets["sql"] == "SELECT * FROM foo"


def test_r_code_snippets_are_escaped(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM "foo"')
    assert 'SELECT * FROM \\"foo\\"' in snippets["r"]


def test_python_code_snippets_are_escaped(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM "foo"')
    assert 'sqlalchemy.text("""SELECT * FROM \\"foo\\""""' in snippets["python"]


class TestUpdateQuickSightVisualisationsLastUpdatedDate:
    @pytest.fixture(autouse=True)
    def setUp(self):
        mock_sts_client = MagicMock()
        self.mock_quicksight_client = MagicMock()
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {"Version": {"DataSetArns": ["testArn"]}}
        }
        boto3_patcher = patch("dataworkspace.apps.datasets.utils.boto3.client")
        mock_boto3_client = boto3_patcher.start()
        mock_boto3_client.side_effect = [
            mock_sts_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
        ]
        yield
        boto3_patcher.stop()

    @pytest.mark.django_db
    def test_spice_visualisation(self):
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "SPICE",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "RelationalTable": {"Schema": "public", "Name": "bar"}
                    }
                },
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the DataSet's LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    def test_direct_query_visualisation_with_relational_table(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "RelationalTable": {"Schema": "public", "Name": "bar"}
                    }
                },
            }
        }
        mock_get_tables_last_updated_date.return_value = datetime.date(2021, 1, 2)

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        assert mock_get_tables_last_updated_date.call_args_list == [
            call("my_database", (("public", "bar"),))
        ]

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the table's last_updated_date
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 2
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_direct_query_visualisation_with_custom_sql(self):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM foo"}
                    }
                },
            }
        }

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to max of Dashboard.LastPublishedTime,
        # Dashboard.LastUpdatedTime,DataSet.LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 3, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_direct_query_visualisation_with_s3_source(self):
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                "PhysicalTableMap": {"00000000-0000-0000-0000-000000000000": {"S3Source": {}}},
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the DataSet's LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_visualisation_with_multiple_data_sets(self):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {"Version": {"DataSetArns": ["testArn", "testArn2"]}}
        }

        self.mock_quicksight_client.describe_data_set.side_effect = [
            {
                "DataSet": {
                    "ImportMode": "SPICE",
                    "DataSetId": "00000000-0000-0000-0000-000000000001",
                    "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                    "PhysicalTableMap": {
                        "00000000-0000-0000-0000-000000000000": {
                            "RelationalTable": {"Schema": "public", "Name": "bar"}
                        },
                    },
                }
            },
            {
                "DataSet": {
                    "ImportMode": "SPICE",
                    "DataSetId": "00000000-0000-0000-0000-000000000002",
                    "LastUpdatedTime": datetime.datetime(2021, 1, 2),
                    "PhysicalTableMap": {
                        "00000000-0000-0000-0000-000000000000": {
                            "RelationalTable": {"Schema": "public", "Name": "bar"}
                        },
                    },
                }
            },
        ]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the most recent DataSet LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 2
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    def test_visualisation_data_set_with_multiple_mappings(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "RelationalTable": {"Schema": "public", "Name": "bar"}
                    },
                    "00000000-0000-0000-0000-000000000001": {
                        "RelationalTable": {"Schema": "public", "Name": "baz"}
                    },
                },
            }
        }
        mock_get_tables_last_updated_date.side_effect = [
            datetime.date(2021, 1, 2),
            datetime.date(2021, 1, 3),
        ]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()
        assert mock_get_tables_last_updated_date.call_args_list == [
            call("my_database", (("public", "bar"),)),
            call("my_database", (("public", "baz"),)),
        ]
        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the most recent table last_updated_date
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 3
        ).replace(tzinfo=pytz.UTC)


class TestUpdateQuickSightVisualisationsRelatedDatasets:
    @pytest.fixture(autouse=True)
    def setUp(self):
        mock_sts_client = MagicMock()
        self.mock_quicksight_client = MagicMock()
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {"Version": {"DataSetArns": ["testArn"]}}
        }
        boto3_patcher = patch("dataworkspace.apps.datasets.utils.boto3.client")
        mock_boto3_client = boto3_patcher.start()
        mock_boto3_client.side_effect = [
            mock_sts_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
        ]
        yield
        boto3_patcher.stop()

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    def test_direct_query_visualisation_with_relational_table(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 1, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "RelationalTable": {"Schema": "public", "Name": "bar"}
                    }
                },
            }
        }
        mock_get_tables_last_updated_date.return_value = datetime.date(2021, 1, 2)
        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="bar")

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                "id", flat=True
            )
        ) == [ds.id]

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_direct_query_visualisation_with_custom_sql(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo"}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [("public", "foo")]

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="foo")

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                "id", flat=True
            )
        ) == [ds.id]


class TestUpdateQuickSightVisualisationsSqlQueries:
    @pytest.fixture(autouse=True)
    def setUp(self):
        mock_sts_client = MagicMock()
        self.mock_quicksight_client = MagicMock()
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {"Version": {"DataSetArns": ["testArn"]}}
        }
        boto3_patcher = patch("dataworkspace.apps.datasets.utils.boto3.client")
        mock_boto3_client = boto3_patcher.start()
        mock_boto3_client.side_effect = [
            mock_sts_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
            self.mock_quicksight_client,
        ]
        yield
        boto3_patcher.stop()

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_creates_sql_query_using_custom_sql(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo"}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [("public", "foo")]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == "00000000-0000-0000-0000-000000000001"
        assert sql_query.is_latest is True
        assert sql_query.sql_query == "SELECT * FROM public.foo"

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_sql_query_no_change_doesnt_create_new_version(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo"}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [("public", "foo")]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == "00000000-0000-0000-0000-000000000001"
        assert sql_query.is_latest is True
        assert sql_query.sql_query == "SELECT * FROM public.foo"

        process_quicksight_dashboard_visualisations()

        assert len(visualisation_link.sql_queries.all()) == 1

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_sql_query_changes_creates_new_version(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo"}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [("public", "foo")]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == "00000000-0000-0000-0000-000000000001"
        assert sql_query.is_latest is True
        assert sql_query.sql_query == "SELECT * FROM public.foo"

        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo WHERE bar = 1"}
                    }
                },
            }
        }
        process_quicksight_dashboard_visualisations()
        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 2

        new_sql_query = visualisation_link.sql_queries.all().order_by("-created_date")[0]
        original_sql_query = visualisation_link.sql_queries.all().order_by("-created_date")[1]

        assert new_sql_query.is_latest is True
        assert new_sql_query.sql_query == "SELECT * FROM public.foo WHERE bar = 1"

        assert original_sql_query.is_latest is False
        assert original_sql_query.sql_query == "SELECT * FROM public.foo"

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_sql_query_changes_multiple_table_mappings(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            "Dashboard": {
                "Version": {"DataSetArns": ["testArn"]},
                "LastPublishedTime": datetime.datetime(2021, 1, 1),
                "LastUpdatedTime": datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo"}
                    },
                    "00000000-0000-0000-0000-000000000001": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.bar"}
                    },
                },
            }
        }
        mock_extract_tables.return_value = [("public", "foo")]

        visualisation_link = VisualisationLinkFactory(visualisation_type="QUICKSIGHT")
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        sql_queries = visualisation_link.sql_queries.order_by("table_id")
        assert len(sql_queries) == 2

        assert str(sql_queries[0].data_set_id) == "00000000-0000-0000-0000-000000000001"
        assert str(sql_queries[0].table_id) == "00000000-0000-0000-0000-000000000000"
        assert sql_queries[0].is_latest is True
        assert sql_queries[0].sql_query == "SELECT * FROM public.foo"

        assert str(sql_queries[1].data_set_id) == "00000000-0000-0000-0000-000000000001"
        assert str(sql_queries[1].table_id) == "00000000-0000-0000-0000-000000000001"
        assert sql_queries[1].is_latest is True
        assert sql_queries[1].sql_query == "SELECT * FROM public.bar"

        self.mock_quicksight_client.describe_data_set.return_value = {
            "DataSet": {
                "ImportMode": "DIRECT_QUERY",
                "DataSetId": "00000000-0000-0000-0000-000000000001",
                "LastUpdatedTime": datetime.datetime(2021, 3, 1),
                "PhysicalTableMap": {
                    "00000000-0000-0000-0000-000000000000": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.foo WHERE bar = 1"}
                    },
                    "00000000-0000-0000-0000-000000000001": {
                        "CustomSql": {"SqlQuery": "SELECT * FROM public.bar"}
                    },
                },
            }
        }
        process_quicksight_dashboard_visualisations()
        visualisation_link.refresh_from_db()

        # only one new query should have been created as the sql changed for one mapping only
        assert len(visualisation_link.sql_queries.all()) == 3

        table_1_sql_queries = visualisation_link.sql_queries.filter(
            table_id="00000000-0000-0000-0000-000000000000"
        ).order_by("-created_date")

        table_2_sql_queries = visualisation_link.sql_queries.filter(
            table_id="00000000-0000-0000-0000-000000000001"
        )

        assert len(table_1_sql_queries) == 2
        assert len(table_2_sql_queries) == 1

        assert table_1_sql_queries[0].is_latest is True
        assert table_1_sql_queries[0].sql_query == "SELECT * FROM public.foo WHERE bar = 1"

        assert table_1_sql_queries[1].is_latest is False
        assert table_1_sql_queries[1].sql_query == "SELECT * FROM public.foo"


class TestLinkSupersetVisualisationsRelatedDatasets:
    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query")
    def test_links_superset_dashboard_to_dataset(self, mock_extract_tables, requests_mock):
        requests_mock.post(
            "http://superset.test/api/v1/security/login", json={"access_token": "123"}
        )
        requests_mock.get(
            "http://superset.test/api/v1/dashboard/1/datasets",
            json={"result": [{"id": 1, "sql": "SELECT * FROM foo"}]},
        )
        mock_extract_tables.return_value = [("public", "foo")]

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="foo")
        visualisation_link = VisualisationLinkFactory(
            visualisation_type="SUPERSET", identifier="1"
        )

        link_superset_visualisations_to_related_datasets()

        assert requests_mock.request_history[0].json() == {
            "username": "dw_user",
            "password": "dw_user_password",
            "provider": "db",
        }
        assert requests_mock.request_history[1].headers["Authorization"] == "Bearer 123"

        visualisation_link.refresh_from_db()
        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                "id", flat=True
            )
        ) == [ds.id]


def get_dsn():
    return database_dsn(settings.DATABASES_DATA["my_database"])


class TestStoreCustomDatasetQueryMetadata:
    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_stores_table_structure_first_run_query_updated_after_table(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 14:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.return_value = "abcdefghijklmnopqrstuvwxyz"

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # change_date should be that of the query because it was created / modified more recently
        # than the underlying tables were last updated
        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 15:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_stores_table_structure_first_run_table_updated_after_query(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 16:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.return_value = "abcdefghijklmnopqrstuvwxyz"

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # change_date should be that of the underlying table because it was updated more recently
        # than the query was created / modified
        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 16:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_multiple_runs_without_change_doesnt_result_in_new_changelog_records(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 14:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.return_value = "abcdefghijklmnopqrstuvwxyz"

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()
        store_custom_dataset_query_table_structures()
        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # There should only be one record record as the structure hasn't changed.
        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 15:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_update_query_where_clause_results_in_data_change_not_structure_change(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 14:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.side_effect = [
            "abcdefghijklmnopqrstuvwxyz",
            "aaaadefghijklmnopqrstuvwxyz",
        ]

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()

        with freeze_time("2021-01-01 16:00:00"):
            query.query = "SELECT * FROM foo WHERE b > 10"
            query.save()

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # The current and previous table structure should be the same as only the
        # where clause has changed.

        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 16:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": [["a", "text"], ["b", "integer"]],
                "data_hash": "aaaadefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }.items()
        )

        assert (
            records[1].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 15:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_update_query_select_clause_results_in_data_change_and_structure_change(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 14:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.side_effect = [
            "abcdefghijklmnopqrstuvwxyz",
            "aaaadefghijklmnopqrstuvwxyz",
        ]

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()

        with freeze_time("2021-01-01 16:00:00"):
            query.query = "SELECT a FROM foo"
            query.save()

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # Neither the current and previous table structure or the current and previous
        # data hash should be the same as the select clause has changed

        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 16:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"]],
                "previous_table_structure": [["a", "text"], ["b", "integer"]],
                "data_hash": "aaaadefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }.items()
        )

        assert (
            records[1].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 15:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )

    @pytest.mark.django_db
    @patch("dataworkspace.apps.datasets.utils.get_tables_last_updated_date")
    @patch("dataworkspace.apps.datasets.utils.get_data_hash")
    def test_update_query_select_clause_and_change_back_results_in_new_changelog_records(
        self, mock_get_data_hash, mock_get_tables_last_updated_date, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            "2021-01-01 14:00", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=pytz.UTC)
        mock_get_data_hash.side_effect = [
            "abcdefghijklmnopqrstuvwxyz",
            "aaaadefghijklmnopqrstuvwxyz",
            "abcdefghijklmnopqrstuvwxyz",
        ]

        with freeze_time("2021-01-01 15:00:00"):
            query = CustomDatasetQueryFactory(
                query="SELECT * FROM foo", database__memorable_name="my_database"
            )

        store_custom_dataset_query_table_structures()

        with freeze_time("2021-01-01 16:00:00"):
            query.query = "SELECT a FROM foo"
            query.save()

        store_custom_dataset_query_table_structures()

        with freeze_time("2021-01-01 17:00:00"):
            query.query = "SELECT * FROM foo"
            query.save()

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog("my_database", query)

        # Both the table structure and data hash should have changed and then changed back
        # as the select clause changed and then changed back

        assert (
            records[0].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 17:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": [["a", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaadefghijklmnopqrstuvwxyz",
            }.items()
        )

        assert (
            records[1].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 16:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"]],
                "previous_table_structure": [["a", "text"], ["b", "integer"]],
                "data_hash": "aaaadefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }.items()
        )

        assert (
            records[2].items()
            >= {
                "change_date": datetime.datetime.strptime(
                    "2021-01-01 15:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=pytz.UTC),
                "table_structure": [["a", "text"], ["b", "integer"]],
                "previous_table_structure": None,
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": None,
            }.items()
        )


class TestSendNotificationEmails:
    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_structure_change_sends_notification_to_structure_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000000",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Column id was added",
                },
            )
        ]

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 1

        assert user_notifications[0].notification == notifications[0]
        assert user_notifications[0].subscription.dataset == ds
        assert user_notifications[0].subscription.user.email == "frank.exampleson@test.com"
        assert str(user_notifications[0].email_id) == "00000000-0000-0000-0000-000000000000"

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_data_change_doesnt_send_notification_to_structure_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaaaghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_no_change_doesnt_send_notification_to_structure_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_structure_change_sends_notification_to_all_changes_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=True
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000000",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Column id was added",
                },
            )
        ]

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 1

        assert user_notifications[0].notification == notifications[0]
        assert user_notifications[0].subscription.dataset == ds
        assert user_notifications[0].subscription.user.email == "frank.exampleson@test.com"
        assert str(user_notifications[0].email_id) == "00000000-0000-0000-0000-000000000000"

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_data_change_sends_notification_to_all_changes_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaaaghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=True
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000001",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Records in the dataset changed",
                },
            )
        ]

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 1

        assert user_notifications[0].notification == notifications[0]
        assert user_notifications[0].subscription.dataset == ds
        assert user_notifications[0].subscription.user.email == "frank.exampleson@test.com"
        assert str(user_notifications[0].email_id) == "00000000-0000-0000-0000-000000000000"

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_no_change_doesnt_send_notification_to_all_changes_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=True
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_structure_change_doesnt_send_notification_to_no_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=False, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_data_change_doesnt_send_notification_to_no_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaaaghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=False, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_no_change_doesnt_send_notification_to_no_change_subscriber(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=False, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_multiple_runs_dont_send_duplicate_notifications(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )
        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000000",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Column id was added",
                },
            )
        ]
        mock_send_email.reset_mock()

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 1

        send_notification_emails()

        assert not mock_send_email.called

        assert len(notifications) == 1
        assert len(user_notifications) == 1

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_mutliple_changelog_records_send_single_notification(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 2,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            },
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "abcdefghijklmnopqrstuvwxyz",
            },
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        # Only most recent change should be emailed
        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000000",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Column id was added",
                },
            ),
        ]

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 1

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_changelog_records_with_no_subscribers_doesnt_send_notifications(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_subscription_after_changelog_gets_processed_doesnt_send_notifications(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

    @pytest.mark.django_db
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID="000000000000000000000000000"
    )
    @override_settings(
        NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID="000000000000000000000000001"
    )
    @patch("dataworkspace.apps.datasets.utils.send_email")
    @patch("dataworkspace.apps.datasets.utils.get_source_table_changelog")
    def test_subscription_after_changelog_gets_processed_but_before_new_structure_change_sends_one_notification(
        self, mock_get_source_table_changelog, mock_send_email, user
    ):
        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            }
        ]
        mock_send_email.return_value = "00000000-0000-0000-0000-000000000000"

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, database__memorable_name="my_database")

        send_notification_emails()

        assert not mock_send_email.called

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 1
        assert len(user_notifications) == 0

        ds.subscriptions.create(
            user=user, notify_on_schema_change=True, notify_on_data_change=False
        )

        mock_get_source_table_changelog.return_value = [
            {
                "change_id": 2,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["name", "text"]],
                "previous_table_structure": [["id", "uuid"], ["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            },
            {
                "change_id": 1,
                "change_date": datetime.datetime(2021, 1, 1, 0, 0).replace(tzinfo=pytz.UTC),
                "table_structure": [["id", "uuid"], ["name", "text"]],
                "previous_table_structure": [["name", "text"]],
                "data_hash": "abcdefghijklmnopqrstuvwxyz",
                "previous_data_hash": "aaaaafghijklmnopqrstuvwxyz",
            },
        ]
        send_notification_emails()

        assert mock_send_email.call_args_list == [
            call(
                "000000000000000000000000000",
                "frank.exampleson@test.com",
                personalisation={
                    "change_date": "01/01/2021 - 00:00:00",
                    "dataset_name": ds.name,
                    "dataset_url": f"dataworkspace.test:8000{ds.get_absolute_url()}",
                    "manage_subscriptions_url": "dataworkspace.test:8000/datasets/email_preferences",
                    "summary": "Column id was removed",
                },
            )
        ]

        notifications = Notification.objects.all()
        user_notifications = UserNotification.objects.all()

        assert len(notifications) == 2
        assert len(user_notifications) == 1


class TestStoreReferenceDatasetMetadata:
    def _get_metadata_records(self, db, table_name):
        with connections[db.memorable_name].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT source_data_modified_utc, table_structure, data_hash_v1::text
                FROM dataflow.metadata
                WHERE table_schema='public'
                AND table_name = '{table_name}'
                ORDER BY source_data_modified_utc DESC
                """
            )
            return cursor.fetchall()

    @pytest.mark.django_db
    @freeze_time("2022-01-01 15:00:00")
    def test_new_metadata_record(self, metadata_db):
        # If no metadata record exists, create one
        rds = ReferenceDatasetFactory.create(published=True)
        with freeze_time("2022-01-01 15:00:00"):
            field1 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="id",
                data_type=2,
                is_identifier=True,
                sort_order=1,
                column_name="field1",
            )
            field2 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="name",
                data_type=1,
                is_display_name=True,
                sort_order=2,
                column_name="field2",
            )
            rds.save_record(
                None,
                {
                    "reference_dataset": rds,
                    field1.column_name: 1,
                    field2.column_name: "A record",
                },
            )
        num_metadata_records = len(self._get_metadata_records(metadata_db, rds.table_name))
        store_reference_dataset_metadata()
        metadata_records = self._get_metadata_records(metadata_db, rds.table_name)
        assert len(metadata_records) == num_metadata_records + 1
        assert metadata_records[0] == (
            datetime.datetime(2022, 1, 1, 15, 0),
            f'[["{field1.column_name}", "integer"], ["{field2.column_name}", "varchar(255)"]]',
            "\\x9de4775b276d45c6fdc740ae770578ed",
        )

    @pytest.mark.django_db
    def test_metadata_only_created_when_update_has_occurred(self, metadata_db):
        # Ensure no metadata record is added if there has been no new updates
        rds = ReferenceDatasetFactory.create(published=True)
        field1 = ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True, sort_order=1
        )
        field2 = ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1, is_display_name=True, sort_order=2
        )
        rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 1,
                field2.column_name: "A record",
            },
        )
        store_reference_dataset_metadata()
        num_metadata_records = len(self._get_metadata_records(metadata_db, rds.table_name))
        store_reference_dataset_metadata()
        assert len(self._get_metadata_records(metadata_db, rds.table_name)) == num_metadata_records

    @pytest.mark.django_db
    def test_structure_change(self, metadata_db):
        # Test that structural changes are logged to the metadata db
        with freeze_time("2022-01-01 15:00:00"):
            rds = ReferenceDatasetFactory.create(published=True)
            field1 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="id",
                data_type=2,
                is_identifier=True,
                sort_order=1,
                column_name="field1",
            )
        store_reference_dataset_metadata()
        num_metadata_records = len(self._get_metadata_records(metadata_db, rds.table_name))

        with freeze_time("2022-01-02 15:00:00"):
            field2 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="name",
                data_type=1,
                is_display_name=True,
                sort_order=2,
                column_name="field2",
            )

        store_reference_dataset_metadata()
        metadata_records = self._get_metadata_records(metadata_db, rds.table_name)
        assert len(metadata_records) == num_metadata_records + 1
        assert metadata_records[0] == (
            datetime.datetime(2022, 1, 2, 15, 0),
            f'[["{field1.column_name}", "integer"], ["{field2.column_name}", "varchar(255)"]]',
            "\\xd41d8cd98f00b204e9800998ecf8427e",
        )

    @pytest.mark.django_db
    def test_data_change(self, metadata_db):
        # Test that data changes are logged to the metadata db
        with freeze_time("2023-01-01 15:00:00"):
            rds = ReferenceDatasetFactory.create(published=True)
            field1 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="id",
                data_type=2,
                is_identifier=True,
                sort_order=1,
                column_name="field1",
            )
            rds.save_record(
                None,
                {
                    "reference_dataset": rds,
                    field1.column_name: 1,
                },
            )
        store_reference_dataset_metadata()
        num_metadata_records = len(self._get_metadata_records(metadata_db, rds.table_name))
        with freeze_time("2023-01-02 15:00:00"):
            rds.save_record(
                None,
                {
                    "reference_dataset": rds,
                    field1.column_name: 2,
                },
            )
        store_reference_dataset_metadata()
        metadata_records = self._get_metadata_records(metadata_db, rds.table_name)
        assert len(metadata_records) == num_metadata_records + 1
        assert metadata_records[0] == (
            datetime.datetime(2023, 1, 2, 15, 0),
            f'[["{field1.column_name}", "integer"]]',
            "\\xe7440c03c0a39364aa1b86b0a8670ebc",
        )

    @pytest.mark.django_db
    def test_related_dataset_data_change(self, metadata_db):
        # Ensure changes to linked reference datasets are picked up
        with freeze_time("2021-01-01 15:00:00"):
            rds = ReferenceDatasetFactory.create(published=True)
            field1 = ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="id",
                data_type=2,
                is_identifier=True,
                sort_order=1,
                column_name="field1",
            )
            linked_rds = ReferenceDatasetFactory.create(published=True)
            ReferenceDatasetFieldFactory.create(
                reference_dataset=linked_rds,
                name="linked",
                data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
                is_identifier=True,
                is_display_name=True,
                sort_order=1,
                column_name="linked",
            )
            ReferenceDatasetFieldFactory.create(
                reference_dataset=rds,
                name="link",
                relationship_name="link",
                column_name="link",
                data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                linked_reference_dataset_field=linked_rds.fields.get(is_identifier=True),
            )
            linked_to_record = linked_rds.save_record(
                None, {"reference_dataset": linked_rds, "linked": "A1"}
            )
            rds.save_record(
                None,
                {
                    "reference_dataset": rds,
                    field1.column_name: 1,
                    "link_id": linked_to_record.id,
                },
            )

        store_reference_dataset_metadata()
        original_metadata = self._get_metadata_records(metadata_db, rds.table_name)
        assert original_metadata[0] == (
            datetime.datetime(2021, 1, 1, 15, 0),
            '[["link", "integer"], ["field1", "integer"]]',
            "\\x51808017c128291ef4e9d509179fabe3",
        )
        with freeze_time("2021-01-02 15:00:00"):
            linked_rds.save_record(
                linked_to_record.id, {"reference_dataset": linked_rds, "linked": "A2"}
            )
        store_reference_dataset_metadata()
        new_metadata = self._get_metadata_records(metadata_db, rds.table_name)
        assert new_metadata[0] == (
            datetime.datetime(2021, 1, 2, 15, 0),
            '[["link", "integer"], ["field1", "integer"]]',
            "\\x6777518eb5a5d30aa2e7267bdb11bb60",
        )
