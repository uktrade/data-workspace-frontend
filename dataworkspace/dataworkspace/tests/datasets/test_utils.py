import datetime
from unittest.mock import call, MagicMock, patch
import pytz

import pytest

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    get_code_snippets_for_query,
    get_code_snippets_for_table,
    link_superset_visualisations_to_related_datasets,
    update_quicksight_visualisations_last_updated_date,
)
from dataworkspace.tests.factories import (
    DataSetFactory,
    SourceTableFactory,
    VisualisationLinkFactory,
)


def test_dataset_type_to_manage_unpublished_permission_codename():
    assert (
        dataset_type_to_manage_unpublished_permission_codename(0)
        == 'datasets.manage_unpublished_reference_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSetType.DATACUT)
        == 'datasets.manage_unpublished_datacut_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSetType.MASTER)
        == 'datasets.manage_unpublished_master_datasets'
    )


@pytest.mark.django_db
def test_get_code_snippets_for_table(metadata_db):
    ds = DataSetFactory.create(type=DataSetType.MASTER)
    sourcetable = SourceTableFactory.create(
        dataset=ds, schema="public", table="MY_LOVELY_TABLE"
    )

    snippets = get_code_snippets_for_table(sourcetable)
    assert """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50""" in snippets['python']
    assert """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50""" in snippets['r']
    assert snippets['sql'] == """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50"""


def test_get_code_snippets_for_query(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM foo')
    assert 'SELECT * FROM foo' in snippets['python']
    assert 'SELECT * FROM foo' in snippets['r']
    assert snippets['sql'] == 'SELECT * FROM foo'


class TestUpdateQuickSightVisualisationsLastUpdatedDate:
    @pytest.fixture(autouse=True)
    def setUp(self):
        mock_sts_client = MagicMock()
        self.mock_quicksight_client = MagicMock()
        self.mock_quicksight_client.describe_dashboard.return_value = {
            'Dashboard': {'Version': {'DataSetArns': ['testArn']}}
        }
        boto3_patcher = patch('dataworkspace.apps.datasets.utils.boto3.client')
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
            'DataSet': {
                'ImportMode': 'SPICE',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the DataSet's LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_direct_query_visualisation_with_relational_table(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                    }
                },
            }
        }
        mock_get_tables_last_updated_date.return_value = datetime.date(2021, 1, 2)

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        assert mock_get_tables_last_updated_date.call_args_list == [
            call('my_database', (('public', 'bar'),))
        ]

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the table's last_updated_date
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 2
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_direct_query_visualisation_with_custom_sql(self):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            'Dashboard': {
                'Version': {'DataSetArns': ['testArn']},
                'LastPublishedTime': datetime.datetime(2021, 1, 1),
                'LastUpdatedTime': datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM foo'}
                    }
                },
            }
        }

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to max of Dashboard.LastPublishedTime,
        # Dashboard.LastUpdatedTime,DataSet.LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 3, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_direct_query_visualisation_with_s3_source(self):
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {'S3Source': {}}
                },
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the DataSet's LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 1
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    def test_visualisation_with_multiple_data_sets(self):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            'Dashboard': {'Version': {'DataSetArns': ['testArn', 'testArn2']}}
        }

        self.mock_quicksight_client.describe_data_set.side_effect = [
            {
                'DataSet': {
                    'ImportMode': 'SPICE',
                    'DataSetId': '1',
                    'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                }
            },
            {
                'DataSet': {
                    'ImportMode': 'SPICE',
                    'DataSetId': '2',
                    'LastUpdatedTime': datetime.datetime(2021, 1, 2),
                }
            },
        ]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()
        # data_source_last_updated should be set to the most recent DataSet LastUpdatedTime
        assert visualisation_link.data_source_last_updated == datetime.datetime(
            2021, 1, 2
        ).replace(tzinfo=pytz.UTC)

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_visualisation_data_set_with_multiple_mappings(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                    },
                    '00000000-0000-0000-0000-000000000001': {
                        'RelationalTable': {'Schema': 'public', 'Name': 'baz'}
                    },
                },
            }
        }
        mock_get_tables_last_updated_date.side_effect = [
            datetime.date(2021, 1, 2),
            datetime.date(2021, 1, 3),
        ]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()
        assert mock_get_tables_last_updated_date.call_args_list == [
            call('my_database', (('public', 'bar'),)),
            call('my_database', (('public', 'baz'),)),
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
            'Dashboard': {'Version': {'DataSetArns': ['testArn']}}
        }
        boto3_patcher = patch('dataworkspace.apps.datasets.utils.boto3.client')
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
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_direct_query_visualisation_with_relational_table(
        self, mock_get_tables_last_updated_date
    ):
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                    }
                },
            }
        }
        mock_get_tables_last_updated_date.return_value = datetime.date(2021, 1, 2)
        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="bar")

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()

        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                'id', flat=True
            )
        ) == [ds.id]

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_direct_query_visualisation_with_custom_sql(self, mock_extract_tables):
        self.mock_quicksight_client.describe_dashboard.return_value = {
            'Dashboard': {
                'Version': {'DataSetArns': ['testArn']},
                'LastPublishedTime': datetime.datetime(2021, 1, 1),
                'LastUpdatedTime': datetime.datetime(2021, 2, 1),
            }
        }
        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '1',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.foo'}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [('public', 'foo')]

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="foo")

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        update_quicksight_visualisations_last_updated_date()

        visualisation_link.refresh_from_db()

        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                'id', flat=True
            )
        ) == [ds.id]


class TestLinkSupersetVisualisationsRelatedDatasets:
    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_links_superset_dashboard_to_dataset(
        self, mock_extract_tables, requests_mock
    ):
        requests_mock.post(
            'http://superset.test/api/v1/security/login', json={'access_token': '123'}
        )
        requests_mock.get(
            'http://superset.test/api/v1/dashboard/1/datasets',
            json={'result': [{'id': 1, 'sql': 'SELECT * FROM foo'}]},
        )
        mock_extract_tables.return_value = [('public', 'foo')]

        ds = DataSetFactory.create(type=DataSetType.MASTER)
        SourceTableFactory.create(dataset=ds, schema="public", table="foo")
        visualisation_link = VisualisationLinkFactory(
            visualisation_type='SUPERSET', identifier='1'
        )

        link_superset_visualisations_to_related_datasets()

        assert requests_mock.request_history[0].json() == {
            'username': 'dw_user',
            'password': 'dw_user_password',
            'provider': 'db',
        }
        assert requests_mock.request_history[1].headers['Authorization'] == 'Bearer 123'

        visualisation_link.refresh_from_db()
        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                'id', flat=True
            )
        ) == [ds.id]
