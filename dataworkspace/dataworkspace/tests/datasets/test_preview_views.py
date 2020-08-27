import psycopg2
import pytest

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.tests import factories


class TestCustomQueryPreviewView:
    @pytest.fixture
    def test_db(self, db):
        yield factories.DatabaseFactory(memorable_name='my_database')

    def test_preview_forbidden_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_DATA_CUT, user_access_type='REQUIRES_AUTHORIZATION',
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=test_db, query='SELECT * FROM a_table',
        )
        response = client.get(
            reverse(
                'datasets:dataset_query_preview',
                kwargs={'dataset_uuid': dataset.id, 'query_id': query.id},
            )
        )
        assert response.status_code == 403

    def test_preview_invalid_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_DATA_CUT, user_access_type='REQUIRES_AUTHENTICATION',
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=test_db, query='SELECT * FROM invalid_table',
        )
        response = client.get(
            reverse(
                'datasets:dataset_query_preview',
                kwargs={'dataset_uuid': dataset.id, 'query_id': query.id},
            )
        )
        response_content = response.content.decode(response.charset)
        assert 'Data Fields' not in response_content
        assert 'No data available' in response_content
        assert 'Download' not in response_content

    @override_settings(DATASET_PREVIEW_NUM_OF_ROWS=20)
    def test_preview_valid_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_DATA_CUT, user_access_type='REQUIRES_AUTHENTICATION',
        )

        # Check if sample data shown correctly
        query1 = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=test_db, query='SELECT 1 as a, 2 as b',
        )
        response = client.get(
            reverse(
                'datasets:dataset_query_preview',
                kwargs={'dataset_uuid': dataset.id, 'query_id': query1.id},
            )
        )
        response_content = response.content.decode(response.charset)
        html = ''.join([s.strip() for s in response_content.splitlines() if s.strip()])
        assert response.status_code == 200
        assert '<li>a</li><li>b</li>' in html  # check fields
        assert (
            '<thead>'
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header ref-data-col-">a</th>'
            '<th class="govuk-table__header ref-data-col-">b</th>'
            '</tr>'
            '</thead>'
            '<tbody>'
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">1</td>'
            '<td class="govuk-table__cell">2</td>'
            '</tr>'
            '</tbody>'
        ) in html  # check sample data
        assert 'Showing all rows from data.' in html
        assert 'Download' in html  # check download button available

        # Check if sample limited to 20 random rows if more data available
        preview_rows = settings.DATASET_PREVIEW_NUM_OF_ROWS
        query2 = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query=f'SELECT * FROM generate_series(1, {preview_rows * 2}) as a;',
        )

        response = client.get(
            reverse(
                'datasets:dataset_query_preview',
                kwargs={'dataset_uuid': dataset.id, 'query_id': query2.id},
            )
        )
        response_content = response.content.decode(response.charset)
        assert (
            f'Showing <strong>{preview_rows}</strong> random rows from data.'
            in response_content
        )

    def _preview_unreviewed_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_DATA_CUT,
            user_access_type='REQUIRES_AUTHENTICATION',
            published=True,
        )
        sql = 'SELECT 1 as a, 2 as b'
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=test_db, query=sql, reviewed=False
        )
        return client.get(
            reverse(
                'datasets:dataset_query_preview',
                kwargs={'dataset_uuid': dataset.id, 'query_id': query.id},
            )
        )

    def test_staff_user_can_preview_unreviewed_datacut(self, staff_client, test_db):
        assert (
            self._preview_unreviewed_datacut(staff_client, test_db).status_code == 200
        )

    def test_normal_user_cannot_preview_unreviewed_datacut(self, client, test_db):
        assert self._preview_unreviewed_datacut(client, test_db).status_code == 403


class TestSourceTablePreviewView:
    @pytest.fixture
    def test_db(self, db):
        database = factories.DatabaseFactory(memorable_name='my_database')
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA['my_database'])
        ) as conn:
            conn.cursor().execute(
                '''
                CREATE TABLE IF NOT EXISTS test_table AS (
                    SELECT 1 as a, 2 as b
                );
            '''
            )
            conn.commit()
            yield database
            conn.cursor().execute('DROP TABLE test_table')

    def test_preview_forbidden_master_dataset(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_MASTER_DATASET, user_access_type='REQUIRES_AUTHORIZATION'
        )
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            name='source_table1',
            database=test_db,
            schema='public',
            table='test_table',
        )
        response = client.get(
            reverse(
                'datasets:dataset_table_preview',
                kwargs={'dataset_uuid': dataset.id, 'table_uuid': source_table.id},
            )
        )
        assert response.status_code == 403

    @override_settings(DATASET_PREVIEW_NUM_OF_ROWS=10)
    def test_preview_table(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSet.TYPE_MASTER_DATASET, user_access_type='REQUIRES_AUTHENTICATION'
        )

        # Check if sample data shown correctly
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            name='source_table1',
            database=test_db,
            schema='public',
            table='test_table',
        )
        response = client.get(
            reverse(
                'datasets:dataset_table_preview',
                kwargs={'dataset_uuid': dataset.id, 'table_uuid': source_table.id},
            )
        )
        response_content = response.content.decode(response.charset)
        html = ''.join([s.strip() for s in response_content.splitlines() if s.strip()])
        assert response.status_code == 200
        assert '<li>a</li><li>b</li>' in html  # check fields
        assert (
            '<thead>'
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header ref-data-col-">a</th>'
            '<th class="govuk-table__header ref-data-col-">b</th>'
            '</tr>'
            '</thead>'
            '<tbody>'
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">1</td>'
            '<td class="govuk-table__cell">2</td>'
            '</tr>'
            '</tbody>'
        ) in html  # check sample data
        assert 'Showing all rows from data.' in html
        assert 'Download' not in html  # check download button available
