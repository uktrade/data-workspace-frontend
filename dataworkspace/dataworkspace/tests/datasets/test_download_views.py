import io
from unittest import mock

import psycopg2
import pytest
from botocore.response import StreamingBody
from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import SourceLink, ReferenceDataset, DataSet
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories


def test_master_dataset_with_access_preview(client, dataset_db):
    ds = factories.DataSetFactory.create(
        type=DataSet.TYPE_MASTER_DATASET,
        user_access_type='REQUIRES_AUTHENTICATION',
        published=True,
    )
    source_table = factories.SourceTableFactory(
        dataset=ds,
        name='source_table1',
        database=dataset_db,
        schema='public',
        table='dataset_test',
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert (
        f'href="/datasets/{ds.id}/table/{source_table.id}/preview"'
        in response.rendered_content
    )
    assert 'Preview' in response.rendered_content


def test_master_dataset_no_access_preview(client, dataset_db):
    ds = factories.DataSetFactory.create(
        type=DataSet.TYPE_MASTER_DATASET,
        user_access_type='REQUIRES_AUTHORIZATION',
        published=True,
    )
    source_table = factories.SourceTableFactory(
        dataset=ds,
        name='source_table1',
        database=dataset_db,
        schema='public',
        table='dataset_test',
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert (
        f'href="/datasets/{ds.id}/table/{source_table.id}/preview"'
        not in response.rendered_content
    )
    assert 'Preview' not in response.rendered_content


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


def test_query_data_cut_preview(client, dataset_db):
    ds = factories.DataSetFactory.create(
        user_access_type='REQUIRES_AUTHENTICATION', published=True,
    )
    cut1 = factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
        reviewed=True,
    )
    cut2 = factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
        reviewed=False,
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200

    # reviewed query should have a preview link
    assert (
        f'href="/datasets/{ds.id}/query/{cut1.id}/preview"' in response.rendered_content
    )
    assert 'Preview' in response.rendered_content

    # non reviewed query shouldn't have a preview link
    assert (
        f'href="/datasets/{ds.id}/query/{cut2.id}/preview"'
        not in response.rendered_content
    )
    assert 'No preview available' in response.rendered_content


def test_query_data_cut_preview_staff_user(staff_client, dataset_db):
    ds = factories.DataSetFactory.create(
        user_access_type='REQUIRES_AUTHENTICATION', published=True,
    )
    cut = factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
        reviewed=False,
    )
    response = staff_client.get(ds.get_absolute_url())

    # non reviewed query should have a preview link
    assert (
        f'href="/datasets/{ds.id}/query/{cut.id}/preview"' in response.rendered_content
    )
    assert 'Preview' in response.rendered_content


def test_query_data_cut_preview_staff_user_no_access(staff_client, dataset_db):
    ds = factories.DataSetFactory.create(
        user_access_type='REQUIRES_AUTHORIZATION', published=True,
    )
    cut = factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
        reviewed=False,
    )
    response = staff_client.get(ds.get_absolute_url())

    # staff user with no access should not have a preview link
    assert (
        f'href="/datasets/{ds.id}/query/{cut.id}/preview"'
        not in response.rendered_content
    )
    assert 'Preview' not in response.rendered_content


def test_link_data_cut_doesnt_have_fields(client):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] is None


def test_link_data_cut_doesnt_have_preview(client):
    ds = factories.DataSetFactory(
        user_access_type='REQUIRES_AUTHENTICATION', published=True
    )
    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert 'No preview available' in response.rendered_content


class TestDatasetViews:
    def test_homepage_unauth(self, unauthenticated_client):
        response = unauthenticated_client.get(reverse('root'))
        assert response.status_code == 403

    def test_homepage(self, client):
        response = client.get(reverse('root'))
        assert response.status_code == 200

    @pytest.mark.parametrize(
        'request_client,factory,published,status',
        [
            ('client', factories.DataSetFactory, True, 200),
            ('client', factories.ReferenceDatasetFactory, True, 200),
            ('client', factories.DataSetFactory, False, 404),
            ('client', factories.ReferenceDatasetFactory, False, 404),
            ('staff_client', factories.DataSetFactory, True, 200),
            ('staff_client', factories.ReferenceDatasetFactory, True, 200),
            ('staff_client', factories.DataSetFactory, False, 200),
            ('staff_client', factories.ReferenceDatasetFactory, False, 200),
        ],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_dataset_detail_view(self, request_client, factory, published, status):
        ds = factory.create(published=published)
        response = request_client.get(ds.get_absolute_url())
        assert response.status_code == status

    def test_deleted_dataset_detail_view(self, client):
        ds = factories.DataSetFactory.create(published=True, deleted=True)
        response = client.get(ds.get_absolute_url())
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_dataset_detail_view_invalid_uuid(self, client):
        response = client.get('/datasets/0c2825e1')
        assert response.status_code == 404

    @override_settings(DEBUG=False, GTM_CONTAINER_ID="test")
    @pytest.mark.parametrize(
        'factory',
        [
            factories.MasterDataSetFactory,
            factories.DatacutDataSetFactory,
            factories.ReferenceDatasetFactory,
        ],
    )
    def test_renders_gtm_push(self, client, factory):
        ds = factory.create(published=True, deleted=False)
        response = client.get(ds.get_absolute_url())
        assert "dataLayer.push({" in response.content.decode(response.charset)

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_reference_dataset_json_download(self, request_client, published):
        linked_rds = factories.ReferenceDatasetFactory.create(published=published)
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds,
            name='id',
            data_type=2,
            is_identifier=True,
            column_name='extid',
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='name', data_type=1, column_name='name',
        )
        rds = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True,
            column_name='extid',
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='name', data_type=1, column_name='name'
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked: id',
            data_type=8,
            linked_reference_dataset_field=linked_rds.fields.get(is_identifier=True),
            relationship_name='linked',
            sort_order=2,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked: name',
            data_type=8,
            linked_reference_dataset_field=linked_rds.fields.get(name='name'),
            relationship_name='linked',
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
                field3.relationship_name + '_id': link_record.id,
            },
        )
        rec2 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 2,
                field2.column_name: 'Ánd again',
                field3.relationship_name: None,
            },
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = request_client.get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'json'},
            )
        )
        assert response.status_code == 200
        assert response.json() == [
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
        ]
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
        )
        assert (
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads
            == download_count + 1
        )

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_reference_dataset_csv_download(self, request_client, published):
        linked_rds = factories.ReferenceDatasetFactory.create(published=published)
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='id', data_type=2, is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name='name', data_type=1
        )
        rds = factories.ReferenceDatasetFactory.create()
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
            name='linked: id',
            relationship_name='linked',
            data_type=8,
            linked_reference_dataset_field=linked_rds.fields.get(is_identifier=True),
            sort_order=3,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked: name',
            relationship_name='linked',
            data_type=8,
            linked_reference_dataset_field=linked_rds.fields.get(name='name'),
            sort_order=4,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto uuid',
            column_name='auto_uuid',
            data_type=9,
            sort_order=5,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='auto id',
            column_name='auto_id',
            data_type=10,
            sort_order=6,
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
                field3.relationship_name + '_id': link_record.id,
            },
        )
        rec2 = rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 2,
                field2.column_name: 'Ánd again',
                field3.relationship_name: None,
            },
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = request_client.get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'csv'},
            )
        )
        assert response.status_code == 200
        assert response.content == (
            b'"id","name","linked: id","linked: name","auto uuid","auto id"\r\n'
            b'1,"Test record",1,"Linked Display Name",%s,1\r\n'
            b'2,"\xc3\x81nd again","","",%s,2\r\n'
            % (str(rec1.auto_uuid).encode(), str(rec2.auto_uuid).encode())
        )
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
        )
        assert (
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads
            == download_count + 1
        )

    def test_reference_dataset_unknown_download(self, client):
        rds = factories.ReferenceDatasetFactory.create(table_name='test_csv')
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, is_identifier=True
        )
        log_count = EventLog.objects.count()
        download_count = rds.number_of_downloads
        response = client.get(
            reverse(
                'datasets:reference_dataset_download',
                kwargs={'dataset_uuid': rds.uuid, 'format': 'madeup'},
            )
        )
        assert response.status_code == 404
        assert EventLog.objects.count() == log_count
        assert (
            ReferenceDataset.objects.get(pk=rds.id).number_of_downloads
            == download_count
        )

    @override_settings(REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS=1)
    @pytest.mark.django_db
    def test_reference_dataset_detail_view(self, client):
        factories.DataSetFactory.create()
        rds = factories.ReferenceDatasetFactory.create(table_name='test_detail_view')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='id', data_type=2, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='name', data_type=1
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name='desc', data_type=1
        )
        rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 1,
                field2.column_name: 'Test record',
                field3.column_name: 'Test Desc 1',
            },
        )
        rds.save_record(
            None,
            {
                'reference_dataset': rds,
                field1.column_name: 2,
                field2.column_name: 'Ánd again',
                field3.column_name: None,
            },
        )

        response = client.get(rds.get_absolute_url())
        assert response.status_code == 200
        assert rds.name.encode('utf-8') in response.content
        assert response.context['record_count'] == 2
        assert response.context['preview_limit'] == 1
        assert response.context['records'].count() == 1
        actual_record = response.context['records'].first()
        assert getattr(actual_record, field1.column_name) == 1
        assert getattr(actual_record, field2.column_name) == 'Test record'
        assert getattr(actual_record, field3.column_name) == 'Test Desc 1'


class TestSourceLinkDownloadView:
    def test_forbidden_dataset(self, client):
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
        response = client.get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            )
        )
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_download_external_file(self, request_client, published):
        dataset = factories.DataSetFactory.create(
            published=published, user_access_type='REQUIRES_AUTHENTICATION'
        )
        link = factories.SourceLinkFactory(
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url='http://example.com',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            ),
            follow=False,
        )
        assert response.status_code == 302
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        )
        assert (
            DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1
        )

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.datasets.views.boto3.client')
    def test_download_local_file(self, mock_client, request_client, published):
        dataset = factories.DataSetFactory.create(
            published=published, user_access_type='REQUIRES_AUTHENTICATION'
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
            'ContentLength': len(b'This is a test file'),
            'Body': StreamingBody(
                io.BytesIO(b'This is a test file'), len(b'This is a test file')
            ),
        }
        response = request_client.get(
            reverse(
                'datasets:dataset_source_link_download',
                kwargs={'dataset_uuid': dataset.id, 'source_link_id': link.id},
            )
        )
        assert response.status_code == 200
        assert list(response.streaming_content)[0] == b'This is a test file'
        assert response['content-length'] == str(len(b'This is a test file'))
        mock_client().get_object.assert_called_with(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key=link.url
        )
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        )
        assert (
            DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1
        )


class TestSourceViewDownloadView:
    def test_forbidden_dataset(self, client):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHORIZATION')
        source_view = factories.SourceViewFactory(dataset=dataset)
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = client.get(source_view.get_absolute_url())
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    def test_missing_view(self, client):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHENTICATION')
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
        )
        download_count = dataset.number_of_downloads
        response = client.get(source_view.get_absolute_url())
        assert response.status_code == 404
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_view_download(self, request_client, published):
        dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE if not exists download_test_table (field2 int,field1 varchar(255));
                TRUNCATE TABLE download_test_table;
                INSERT INTO download_test_table VALUES(1, 'record1');
                INSERT INTO download_test_table VALUES(2, 'record2');
                CREATE OR REPLACE VIEW download_test_view AS SELECT * FROM download_test_table;
                '''
            )

        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHENTICATION', published=published
        )
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
            schema='public',
            view='download_test_view',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(source_view.get_absolute_url())
        assert response.status_code == 200
        assert (
            b''.join(response.streaming_content)
            == b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD
        )
        assert (
            DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1
        )

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_materialized_view_download(self, request_client, published):
        dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
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
        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHENTICATION', published=published
        )
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name='my_database'),
            schema='public',
            view='materialized_test_view',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(source_view.get_absolute_url())
        assert response.status_code == 200
        assert (
            b''.join(response.streaming_content)
            == b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD
        )
        assert (
            DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1
        )


class TestCustomQueryDownloadView:
    def _get_dsn(self):
        return database_dsn(settings.DATABASES_DATA['my_database'])

    def _get_database(self):
        return factories.DatabaseFactory(memorable_name='my_database')

    def _create_query(self, sql, reviewed=True, published=True):
        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
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
        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHENTICATION', published=published
        )
        return factories.CustomDatasetQueryFactory(
            dataset=dataset, database=self._get_database(), query=sql, reviewed=reviewed
        )

    def test_forbidden_dataset(self, client):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHORIZATION')
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=self._get_database(),
            query='SELECT * FROM a_table',
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = client.get(query.get_absolute_url())
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    def test_invalid_sql(self, client):
        query = self._create_query('SELECT * FROM table_that_does_not_exist;')
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

    def test_dangerous_sql(self, client):
        # Test drop table
        query = self._create_query('DROP TABLE custom_query_test;')
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT to_regclass(\'custom_query_test\')')
            assert cursor.fetchone()[0] == 'custom_query_test'

        # Test delete records
        query = self._create_query('DELETE FROM custom_query_test;')
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            assert cursor.fetchone()[0] == 3

        # Test update records
        query = self._create_query('UPDATE custom_query_test SET name=\'updated\';')
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM custom_query_test WHERE name=\'updated\''
            )
            assert cursor.fetchone()[0] == 0

        # Test insert record
        query = self._create_query(
            'INSERT INTO custom_query_test (id, name) VALUES(4, \'added\')'
        )
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            assert cursor.fetchone()[0] == 3

    @pytest.mark.parametrize(
        'request_client,published',
        [('client', True), ('staff_client', True), ('staff_client', False)],
        indirect=['request_client'],
    )
    @pytest.mark.django_db
    def test_valid_sql(self, request_client, published):
        query = self._create_query(
            'SELECT * FROM custom_query_test WHERE id IN (1, 3)', published=published
        )
        log_count = EventLog.objects.count()
        download_count = query.dataset.number_of_downloads
        response = request_client.get(query.get_absolute_url())
        assert response.status_code == 200
        assert b''.join(response.streaming_content) == (
            b'"id","name","date"\r\n1,"the first record",""\r\n'
            b'3,"the last record",""\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert (
            EventLog.objects.latest().event_type
            == EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
        )
        assert (
            DataSet.objects.get(pk=query.dataset.id).number_of_downloads
            == download_count + 1
        )

    @pytest.mark.parametrize(
        "request_client, reviewed, status",
        (
            ("sme_client", False, 403),
            ("sme_client", True, 200),
            ("staff_client", False, 200),
            ("staff_client", True, 200),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_only_superuser_can_download_unreviewed_query(
        self, request_client, reviewed, status
    ):
        query = self._create_query(
            'SELECT * FROM custom_query_test', published=False, reviewed=reviewed
        )

        response = request_client.get(query.get_absolute_url())
        assert response.status_code == status
