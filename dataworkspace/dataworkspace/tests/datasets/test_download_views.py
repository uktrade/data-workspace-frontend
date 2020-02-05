import io

import mock
import psycopg2
import pytest
from botocore.response import StreamingBody
from django.conf import settings
from django.urls import reverse
from psycopg2 import connect

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import SourceLink, ReferenceDataset, DataSet
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase


@pytest.fixture
def dataset_db():
    database = factories.DatabaseFactory(memorable_name='my_database')
    with psycopg2.connect(database_dsn(settings.DATABASES_DATA['my_database'])) as conn:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS dataset_test (
                id INT,
                name VARCHAR(255),
                date DATE
            );

            CREATE TABLE IF NOT EXISTS dataset_test2 (
                id INT,
                name VARCHAR(255)
            );

            CREATE OR REPLACE VIEW dataset_view AS (SELECT * FROM dataset_test);
            '''
        )

    return database


def test_master_dataset_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceTableFactory(
        dataset=ds,
        name='d1',
        database=dataset_db,
        schema='public',
        table='dataset_test',
    )
    factories.SourceTableFactory(
        dataset=ds,
        name='d2',
        database=dataset_db,
        schema='public',
        table='dataset_test2',
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == [
        'dataset_test.id',
        'dataset_test.name',
        'dataset_test.date',
        'dataset_test2.id',
        'dataset_test2.name',
    ]


def test_view_data_cut_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceViewFactory(
        dataset=ds, database=dataset_db, schema='public', view='dataset_view'
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == ['id', 'name', 'date']


def test_query_data_cut_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == ['customid', 'customname']


def test_link_data_cut_doesnt_have_fields(client):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] is None


class TestDatasetViews(BaseTestCase):
    def test_homepage_unauth(self):
        response = self.client.get(reverse('root'))
        self.assertEqual(response.status_code, 403)

    def test_homepage(self):
        response = self._authenticated_get(reverse('root'))
        self.assertEqual(response.status_code, 200)

    def test_dataset_detail_view_unpublished(self):
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(published=False)
        factories.SourceLinkFactory(dataset=ds)
        factories.SourceLinkFactory(dataset=ds)
        response = self._authenticated_get(ds.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_dataset_detail_view_published(self):
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(published=True)
        sl1 = factories.SourceLinkFactory(dataset=ds)
        sl2 = factories.SourceLinkFactory(dataset=ds)
        response = self._authenticated_get(ds.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ds.name)
        self.assertContains(response, sl1.name, 1)
        self.assertContains(response, sl2.name, 1)

    def test_reference_dataset_detail_view(self):
        factories.DataSetFactory.create()
        rds = factories.ReferenceDatasetFactory.create(table_name='test_detail_view')
        factories.ReferenceDatasetFieldFactory(reference_dataset=rds)
        response = self._authenticated_get(rds.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rds.name)

    def test_reference_dataset_json_download(self):
        linked_rds = factories.ReferenceDatasetFactory.create(table_name='test_json')
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='id', data_type=2, is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='name', data_type=1, is_display_name=True
        )
        rds = factories.ReferenceDatasetFactory.create(table_name='test_jso2')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='id', data_type=2, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='name', data_type=1
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked',
            data_type=8,
            linked_reference_dataset=linked_rds,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto uuid',
            column_name='auto_uuid',
            data_type=9,
            sort_order=4,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto id',
            column_name='auto_id',
            data_type=10,
            sort_order=5,
        )
        link_record = linked_rds.save_record(
            None,
            {
                'reference_dataset': linked_rds,
                linked_field1.column_name: 1,
                linked_field2.column_name: 'Linked Display Name',
            },
        )

        rec1 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 1,
                field2.column_name: 'Test record',
                field3.column_name: link_record,
            },
        )
        rec2 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 2,
                field2.column_name: 'Ánd again',
                field3.column_name: None,
            },
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = self._authenticated_get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'json'},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    'id': 1,
                    'linked: id': 1,
                    'linked: name': 'Linked Display Name',
                    'name': 'Test record',
                    'auto uuid': str(rec1.auto_uuid),
                    'auto id': 1,
                },
                {
                    'id': 2,
                    'linked: id': None,
                    'linked: name': None,
                    'name': 'Ánd again',
                    'auto uuid': str(rec2.auto_uuid),
                    'auto id': 2,
                },
            ],
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
        )
        self.assertEqual(
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads,
            download_count + 1,
        )

    def test_reference_dataset_csv_download(self):
        linked_rds = factories.ReferenceDatasetFactory.create(table_name='test_csv')
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='id', data_type=2, is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='name', data_type=1, is_display_name=True
        )
        rds = factories.ReferenceDatasetFactory.create(table_name='test_csv2')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True,
            sort_order=1,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='name', data_type=1, sort_order=2
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked',
            data_type=8,
            linked_reference_dataset=linked_rds,
            sort_order=3,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto uuid',
            column_name='auto_uuid',
            data_type=9,
            sort_order=4,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto id',
            column_name='auto_id',
            data_type=10,
            sort_order=5,
        )
        link_record = linked_rds.save_record(
            None,
            {
                'reference_dataset': linked_rds,
                linked_field1.column_name: 1,
                linked_field2.column_name: 'Linked Display Name',
            },
        )
        rec1 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 1,
                field2.column_name: 'Test record',
                field3.column_name: link_record,
            },
        )
        rec2 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 2,
                field2.column_name: 'Ánd again',
                field3.column_name: None,
            },
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = self._authenticated_get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'csv'},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content,
            b'"id","name","linked: id","linked: name","auto uuid","auto id"\r\n'
            b'1,"Test record",1,"Linked Display Name",%s,1\r\n'
            b'2,"\xc3\x81nd again","","",%s,2\r\n'
            % (str(rec1.auto_uuid).encode(), str(rec2.auto_uuid).encode()),
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
        )
        self.assertEqual(
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads,
            download_count + 1,
        )

    def test_reference_dataset_unknown_download(self):
        rds = factories.ReferenceDatasetFactory.create(table_name='test_csv')
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, is_identifier=True
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = self._authenticated_get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'madeup'},
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(EventLog.objects.count(), log_count)
        self.assertEqual(
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads, download_count
        )


class TestSourceLinkDownloadView(BaseTestCase):
    def test_forbidden_dataset(self):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type='REQUIRES_AUTHORIZATION'
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url='http://example.com',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count
        )

    def test_download_external_file(self):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type='REQUIRES_AUTHENTICATION'
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url='http://example.com',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            )
        )
        self.assertRedirects(
            response, 'http://example.com', fetch_redirect_response=False
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
        )
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count + 1
        )

    @mock.patch('dataworkspace.apps.datasets.views.boto3.client')
    def test_download_local_file(self, mock_client):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type='REQUIRES_AUTHENTICATION'
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_LOCAL,
            url='s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.txt',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        mock_client().get_object.return_value = {
            'ContentType': 'text/plain',
            'Body': StreamingBody(
                io.BytesIO(b'This is a test file'), len(b'This is a test file')
            ),
        }
        response = self._authenticated_get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.streaming_content)[0], b'This is a test file')
        mock_client().get_object.assert_called_with(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key=link.url
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
        )
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count + 1
        )


class TestSourceViewDownloadView(BaseTestCase):
    databases = ['default', 'my_database']

    def test_forbidden_dataset(self):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHORIZATION')
        source_view = factories.SourceViewFactory(dataset=dataset)
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(source_view.get_absolute_url())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count
        )

    def test_missing_view(self):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHENTICATION')
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
        )
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(source_view.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count
        )

    def test_view_download(self):
        dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE if not exists download_test_table (field2 int,field1 varchar(255));
                TRUNCATE TABLE download_test_table;
                INSERT INTO download_test_table VALUES(1, 'record1');
                INSERT INTO download_test_table VALUES(2, 'record2');
                CREATE OR REPLACE VIEW download_test_view AS SELECT * FROM download_test_table;
                '''
            )

        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHENTICATION')
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
            schema='public',
            view='download_test_view',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(source_view.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b''.join(response.streaming_content),
            b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n',
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD,
        )
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count + 1
        )

    def test_materialized_view_download(self):
        dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE if not exists materialized_test_table (field2 int,field1 varchar(255));
                TRUNCATE TABLE materialized_test_table;
                INSERT INTO materialized_test_table VALUES(1, 'record1');
                INSERT INTO materialized_test_table VALUES(2, 'record2');
                DROP MATERIALIZED VIEW IF EXISTS materialized_test_view;
                CREATE MATERIALIZED VIEW materialized_test_view AS
                SELECT * FROM materialized_test_table;
                '''
            )
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHENTICATION')
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
            schema='public',
            view='materialized_test_view',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(source_view.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b''.join(response.streaming_content),
            b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n',
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD,
        )
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count + 1
        )


class TestCustomQueryDownloadView(BaseTestCase):
    databases = ['default', 'my_database']

    def setUp(self):
        super().setUp()
        self.database = factories.DatabaseFactory(memorable_name='my_database')
        self.dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS custom_query_test (
                    id INT,
                    name VARCHAR(255),
                    date DATE
                );
                TRUNCATE TABLE custom_query_test;
                INSERT INTO custom_query_test VALUES(1, 'the first record', NULL);
                INSERT INTO custom_query_test VALUES(2, 'the second record', '2019-01-01');
                INSERT INTO custom_query_test VALUES(3, 'the last record', NULL);
                '''
            )

    def _create_query(self, sql):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHENTICATION')
        return factories.CustomDatasetQueryFactory(
            dataset=dataset, database=self.database, query=sql
        )

    def test_forbidden_dataset(self):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHORIZATION')
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=self.database, query='SELECT * FROM a_table'
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = self._authenticated_get(query.get_absolute_url())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)
        self.assertEqual(
            DataSet.objects.get(pk=dataset.id).number_of_downloads, download_count
        )

    def test_invalid_sql(self):
        query = self._create_query('SELECT * FROM table_that_does_not_exist;')
        self.assertRaises(
            Exception, lambda _: self._authenticated_get(query.get_absolute_url())
        )

    def test_dangerous_sql(self):
        # Test drop table
        query = self._create_query('DROP TABLE custom_query_test;')
        self.assertRaises(
            Exception, lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT to_regclass(\'custom_query_test\')')
            self.assertEqual(cursor.fetchone()[0], 'custom_query_test')

        # Test delete records
        query = self._create_query('DELETE FROM custom_query_test;')
        self.assertRaises(
            Exception, lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            self.assertEqual(cursor.fetchone()[0], 3)

        # Test update records
        query = self._create_query('UPDATE custom_query_test SET name=\'updated\';')
        self.assertRaises(
            Exception, lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM custom_query_test WHERE name=\'updated\''
            )
            self.assertEqual(cursor.fetchone()[0], 0)

        # Test insert record
        query = self._create_query(
            'INSERT INTO custom_query_test (id, name) VALUES(4, \'added\')'
        )
        self.assertRaises(
            Exception, lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            self.assertEqual(cursor.fetchone()[0], 3)

    def test_valid_sql(self):
        query = self._create_query('SELECT * FROM custom_query_test WHERE id IN (1, 3)')
        log_count = EventLog.objects.count()
        download_count = query.dataset.number_of_downloads
        response = self._authenticated_get(query.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b''.join(response.streaming_content),
            b'"id","name","date"\r\n1,"the first record",""\r\n'
            b'3,"the last record",""\r\n"Number of rows: 2"\r\n',
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
        )
        self.assertEqual(
            DataSet.objects.get(pk=query.dataset.id).number_of_downloads,
            download_count + 1,
        )
