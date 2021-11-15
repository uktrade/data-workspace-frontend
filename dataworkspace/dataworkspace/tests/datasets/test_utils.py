import datetime
from unittest.mock import call, MagicMock, patch
import pytz

from django.conf import settings
from freezegun import freeze_time
import pytest

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    get_code_snippets_for_query,
    get_code_snippets_for_table,
    link_superset_visualisations_to_related_datasets,
    process_quicksight_dashboard_visualisations,
    store_custom_dataset_query_table_structures,
)
from dataworkspace.datasets_db import get_custom_dataset_query_changelog
from dataworkspace.tests.factories import (
    CustomDatasetQueryFactory,
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
    assert (
        """SELECT * FROM \\"public\\".\\"MY_LOVELY_TABLE\\" LIMIT 50"""
        in snippets['python']
    )
    assert (
        """SELECT * FROM \\"public\\".\\"MY_LOVELY_TABLE\\" LIMIT 50""" in snippets['r']
    )
    assert snippets['sql'] == """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50"""


def test_get_code_snippets_for_query(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM foo')
    assert 'SELECT * FROM foo' in snippets['python']
    assert 'SELECT * FROM foo' in snippets['r']
    assert snippets['sql'] == 'SELECT * FROM foo'


def test_r_code_snippets_are_escaped(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM "foo"')
    assert 'SELECT * FROM \\"foo\\"' in snippets['r']


def test_python_code_snippets_are_escaped(metadata_db):
    snippets = get_code_snippets_for_query('SELECT * FROM "foo"')
    assert 'sqlalchemy.text(\"""SELECT * FROM \\"foo\\"\"""' in snippets['python']


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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                    }
                },
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
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
        process_quicksight_dashboard_visualisations()

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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM foo'}
                    }
                },
            }
        }

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
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
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {'S3Source': {}}
                },
            }
        }
        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

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
                    'DataSetId': '00000000-0000-0000-0000-000000000001',
                    'LastUpdatedTime': datetime.datetime(2021, 1, 1),
                    'PhysicalTableMap': {
                        '00000000-0000-0000-0000-000000000000': {
                            'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                        },
                    },
                }
            },
            {
                'DataSet': {
                    'ImportMode': 'SPICE',
                    'DataSetId': '00000000-0000-0000-0000-000000000002',
                    'LastUpdatedTime': datetime.datetime(2021, 1, 2),
                    'PhysicalTableMap': {
                        '00000000-0000-0000-0000-000000000000': {
                            'RelationalTable': {'Schema': 'public', 'Name': 'bar'}
                        },
                    },
                }
            },
        ]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
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
        process_quicksight_dashboard_visualisations()
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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
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
        process_quicksight_dashboard_visualisations()

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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
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
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert list(
            visualisation_link.visualisation_catalogue_item.datasets.all().values_list(
                'id', flat=True
            )
        ) == [ds.id]


class TestUpdateQuickSightVisualisationsSqlQueries:
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
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_creates_sql_query_using_custom_sql(self, mock_extract_tables):
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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.foo'}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [('public', 'foo')]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == '00000000-0000-0000-0000-000000000001'
        assert sql_query.is_latest is True
        assert sql_query.sql_query == 'SELECT * FROM public.foo'

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_sql_query_no_change_doesnt_create_new_version(self, mock_extract_tables):
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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.foo'}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [('public', 'foo')]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == '00000000-0000-0000-0000-000000000001'
        assert sql_query.is_latest is True
        assert sql_query.sql_query == 'SELECT * FROM public.foo'

        process_quicksight_dashboard_visualisations()

        assert len(visualisation_link.sql_queries.all()) == 1

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_sql_query_changes_creates_new_version(self, mock_extract_tables):
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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.foo'}
                    }
                },
            }
        }
        mock_extract_tables.return_value = [('public', 'foo')]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 1

        sql_query = visualisation_link.sql_queries.all()[0]

        assert str(sql_query.data_set_id) == '00000000-0000-0000-0000-000000000001'
        assert sql_query.is_latest is True
        assert sql_query.sql_query == 'SELECT * FROM public.foo'

        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {
                            'SqlQuery': 'SELECT * FROM public.foo WHERE bar = 1'
                        }
                    }
                },
            }
        }
        process_quicksight_dashboard_visualisations()
        visualisation_link.refresh_from_db()

        assert len(visualisation_link.sql_queries.all()) == 2

        new_sql_query = visualisation_link.sql_queries.all().order_by('-created_date')[
            0
        ]
        original_sql_query = visualisation_link.sql_queries.all().order_by(
            '-created_date'
        )[1]

        assert new_sql_query.is_latest is True
        assert new_sql_query.sql_query == 'SELECT * FROM public.foo WHERE bar = 1'

        assert original_sql_query.is_latest is False
        assert original_sql_query.sql_query == 'SELECT * FROM public.foo'

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.extract_queried_tables_from_sql_query')
    def test_sql_query_changes_multiple_table_mappings(self, mock_extract_tables):
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
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.foo'}
                    },
                    '00000000-0000-0000-0000-000000000001': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.bar'}
                    },
                },
            }
        }
        mock_extract_tables.return_value = [('public', 'foo')]

        visualisation_link = VisualisationLinkFactory(visualisation_type='QUICKSIGHT')
        process_quicksight_dashboard_visualisations()

        visualisation_link.refresh_from_db()

        sql_queries = visualisation_link.sql_queries.order_by('table_id')
        assert len(sql_queries) == 2

        assert str(sql_queries[0].data_set_id) == '00000000-0000-0000-0000-000000000001'
        assert str(sql_queries[0].table_id) == '00000000-0000-0000-0000-000000000000'
        assert sql_queries[0].is_latest is True
        assert sql_queries[0].sql_query == 'SELECT * FROM public.foo'

        assert str(sql_queries[1].data_set_id) == '00000000-0000-0000-0000-000000000001'
        assert str(sql_queries[1].table_id) == '00000000-0000-0000-0000-000000000001'
        assert sql_queries[1].is_latest is True
        assert sql_queries[1].sql_query == 'SELECT * FROM public.bar'

        self.mock_quicksight_client.describe_data_set.return_value = {
            'DataSet': {
                'ImportMode': 'DIRECT_QUERY',
                'DataSetId': '00000000-0000-0000-0000-000000000001',
                'LastUpdatedTime': datetime.datetime(2021, 3, 1),
                'PhysicalTableMap': {
                    '00000000-0000-0000-0000-000000000000': {
                        'CustomSql': {
                            'SqlQuery': 'SELECT * FROM public.foo WHERE bar = 1'
                        }
                    },
                    '00000000-0000-0000-0000-000000000001': {
                        'CustomSql': {'SqlQuery': 'SELECT * FROM public.bar'}
                    },
                },
            }
        }
        process_quicksight_dashboard_visualisations()
        visualisation_link.refresh_from_db()

        # only one new query should have been created as the sql changed for one mapping only
        assert len(visualisation_link.sql_queries.all()) == 3

        table_1_sql_queries = visualisation_link.sql_queries.filter(
            table_id='00000000-0000-0000-0000-000000000000'
        ).order_by('-created_date')

        table_2_sql_queries = visualisation_link.sql_queries.filter(
            table_id='00000000-0000-0000-0000-000000000001'
        )

        assert len(table_1_sql_queries) == 2
        assert len(table_2_sql_queries) == 1

        assert table_1_sql_queries[0].is_latest is True
        assert (
            table_1_sql_queries[0].sql_query == 'SELECT * FROM public.foo WHERE bar = 1'
        )

        assert table_1_sql_queries[1].is_latest is False
        assert table_1_sql_queries[1].sql_query == 'SELECT * FROM public.foo'


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


def get_dsn():
    return database_dsn(settings.DATABASES_DATA['my_database'])


class TestStoreCustomDatasetQueryTableStructures:
    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_stores_table_structure_first_run_query_updated_after_table(
        self, mock_get_tables_last_updated_date, metadata_db, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            '2021-01-01 14:00', '%Y-%m-%d %H:%M'
        ).replace(tzinfo=pytz.UTC)

        with freeze_time('2021-01-01 15:00:00'):
            query = CustomDatasetQueryFactory(
                query='SELECT * FROM foo', database__memorable_name='my_database'
            )

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog('my_database', query)

        # change_date should be that of the query because it was created / modified more recently
        # than the underlying tables were last updated
        assert records == [
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 15:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"], ["b", "integer"]]',
            },
        ]

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_stores_table_structure_first_run_table_updated_after_query(
        self, mock_get_tables_last_updated_date, metadata_db, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            '2021-01-01 16:00', '%Y-%m-%d %H:%M'
        ).replace(tzinfo=pytz.UTC)

        with freeze_time('2021-01-01 15:00:00'):
            query = CustomDatasetQueryFactory(
                query='SELECT * FROM foo', database__memorable_name='my_database'
            )

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog('my_database', query)

        # change_date should be that of the underlying table because it was updated more recently
        # than the query was created / modified
        assert records == [
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 16:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"], ["b", "integer"]]',
            },
        ]

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_multiple_runs_without_change_doesnt_result_in_new_changelog_records(
        self, mock_get_tables_last_updated_date, metadata_db, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            '2021-01-01 14:00', '%Y-%m-%d %H:%M'
        ).replace(tzinfo=pytz.UTC)

        with freeze_time('2021-01-01 15:00:00'):
            query = CustomDatasetQueryFactory(
                query='SELECT * FROM foo', database__memorable_name='my_database'
            )

        store_custom_dataset_query_table_structures()
        store_custom_dataset_query_table_structures()
        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog('my_database', query)

        # There should only be one record record as the structure hasn't changed.
        assert records == [
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 15:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"], ["b", "integer"]]',
            },
        ]

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_update_query_where_clause_doesnt_result_in_new_changelog_record(
        self, mock_get_tables_last_updated_date, metadata_db, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            '2021-01-01 14:00', '%Y-%m-%d %H:%M'
        ).replace(tzinfo=pytz.UTC)

        with freeze_time('2021-01-01 15:00:00'):
            query = CustomDatasetQueryFactory(
                query='SELECT * FROM foo', database__memorable_name='my_database'
            )

        store_custom_dataset_query_table_structures()

        with freeze_time('2021-01-01 16:00:00'):
            query.query = 'SELECT * FROM foo WHERE b > 10'
            query.save()

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog('my_database', query)

        # There should only be one record record as the structure hasn't changed

        assert records == [
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 15:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"], ["b", "integer"]]',
            },
        ]

    @pytest.mark.django_db
    @patch('dataworkspace.apps.datasets.utils.get_tables_last_updated_date')
    def test_update_query_select_clause_results_in_new_changelog_record(
        self, mock_get_tables_last_updated_date, metadata_db, test_dataset
    ):
        mock_get_tables_last_updated_date.return_value = datetime.datetime.strptime(
            '2021-01-01 14:00', '%Y-%m-%d %H:%M'
        ).replace(tzinfo=pytz.UTC)

        with freeze_time('2021-01-01 15:00:00'):
            query = CustomDatasetQueryFactory(
                query='SELECT * FROM foo', database__memorable_name='my_database'
            )

        store_custom_dataset_query_table_structures()

        with freeze_time('2021-01-01 16:00:00'):
            query.query = 'SELECT a FROM foo'
            query.save()

        store_custom_dataset_query_table_structures()

        records = get_custom_dataset_query_changelog('my_database', query)

        # There should be two records as the query structure has changed

        assert records == [
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 16:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"]]',
            },
            {
                'change_date': datetime.datetime.strptime(
                    '2021-01-01 15:00', '%Y-%m-%d %H:%M'
                ).replace(tzinfo=pytz.UTC),
                'change_type': 'Table structure updated',
                'table_structure': '[["a", "text"], ["b", "integer"]]',
            },
        ]
