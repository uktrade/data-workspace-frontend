import io

from botocore.response import StreamingBody
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from psycopg2 import connect

import mock

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import SourceLink
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase


class TestDatasetViews(BaseTestCase):
    def test_homepage_unauth(self):
        response = self.client.get(reverse('root'))
        self.assertEqual(response.status_code, 403)

    def test_homepage(self):
        response = self._authenticated_get(reverse('root'))
        self.assertEqual(response.status_code, 200)

    def test_homepage_group_list(self):
        g1 = factories.DataGroupingFactory.create()
        g2 = factories.DataGroupingFactory.create()
        g3 = factories.DataGroupingFactory.create()
        g3.delete()

        response = self._authenticated_get(reverse('root'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, g1.name, 1)
        self.assertContains(response, g2.name, 1)

        # Do not show deleted groups
        self.assertNotContains(response, g3.name)

    def test_group_detail_view(self):
        group = factories.DataGroupingFactory.create()

        ds1 = factories.DataSetFactory.create(grouping=group, published=True)
        ds2 = factories.DataSetFactory.create(grouping=group, published=False)
        ds3 = factories.DataSetFactory.create()
        ds4 = factories.DataSetFactory.create(grouping=group, published=False)
        ds4.delete()

        rds1 = factories.ReferenceDatasetFactory(group=group, published=True, table_name='rds1')
        rds2 = factories.ReferenceDatasetFactory(group=group, published=False, table_name='rds2')
        rds3 = factories.ReferenceDatasetFactory()
        rds4 = factories.ReferenceDatasetFactory(group=group, published=False, table_name='rds3')
        rds4.delete()

        response = self._authenticated_get(
            reverse('catalogue:datagroup_item', kwargs={'slug': group.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Ensure datasets in group are displayed
        self.assertContains(response, ds1.name, 1)
        self.assertContains(response, rds1.name, 1)

        # Ensure unpublished datasets are not displayed
        self.assertContains(response, ds2.name, 0)
        self.assertContains(response, rds2.name, 0)

        # Ensure datasets not in group are not displayed
        self.assertNotContains(response, ds3.name)
        self.assertNotContains(response, rds3.name)

        # Ensure deleted datasets are not displayed
        self.assertNotContains(response, ds4.name)
        self.assertNotContains(response, rds4.name)

    def test_dataset_detail_view_unpublished(self):
        group = factories.DataGroupingFactory.create()
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(grouping=group, published=False)
        factories.SourceLinkFactory(dataset=ds)
        factories.SourceLinkFactory(dataset=ds)
        response = self._authenticated_get(
            reverse('catalogue:dataset_fullpath', kwargs={
                'group_slug': group.slug,
                'set_slug': ds.slug
            })
        )
        self.assertEqual(response.status_code, 404)

    def test_dataset_detail_view_published(self):
        group = factories.DataGroupingFactory.create()
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(grouping=group, published=True)
        sl1 = factories.SourceLinkFactory(dataset=ds)
        sl2 = factories.SourceLinkFactory(dataset=ds)
        response = self._authenticated_get(
            reverse('catalogue:dataset_fullpath', kwargs={
                'group_slug': group.slug,
                'set_slug': ds.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ds.name)
        self.assertContains(response, sl1.name, 1)
        self.assertContains(response, sl2.name, 1)

    def test_reference_dataset_detail_view(self):
        group = factories.DataGroupingFactory.create()
        factories.DataSetFactory.create()
        rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_detail_view')
        factories.ReferenceDatasetFieldFactory(
            reference_dataset=rds
        )
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rds.name)

    def test_reference_dataset_json_download(self):
        group = factories.DataGroupingFactory.create()
        linked_rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_json')
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds,
            name='id',
            data_type=2,
            is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds,
            name='name',
            data_type=1,
            is_display_name=True
        )
        rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_jso2')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='name',
            data_type=1,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='linked',
            data_type=8,
            linked_reference_dataset=linked_rds
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
        link_record = linked_rds.save_record(None, {
            'reference_dataset': linked_rds,
            linked_field1.column_name: 1,
            linked_field2.column_name: 'Linked Display Name'
        })

        rec1 = rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 1,
            field2.column_name: 'Test record',
            field3.column_name: link_record
        })
        rec2 = rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 2,
            field2.column_name: 'Ánd again',
            field3.column_name: None,
        })
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'json',
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            'id': 1,
            'linked: ID': 1,
            'linked: Name': 'Linked Display Name',
            'name': 'Test record',
            'auto uuid': str(rec1.auto_uuid),
            'auto id': 1,
        }, {
            'id': 2,
            'linked: ID': None,
            'linked: Name': None,
            'name': 'Ánd again',
            'auto uuid': str(rec2.auto_uuid),
            'auto id': 2,
        }])
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
        )

    def test_reference_dataset_csv_download(self):
        group = factories.DataGroupingFactory.create()
        linked_rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_csv')
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds,
            name='id',
            data_type=2,
            is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds,
            name='name',
            data_type=1,
            is_display_name=True
        )
        rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_csv2')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True,
            sort_order=1,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='name',
            data_type=1,
            sort_order=2,
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
        link_record = linked_rds.save_record(None, {
            'reference_dataset': linked_rds,
            linked_field1.column_name: 1,
            linked_field2.column_name: 'Linked Display Name'
        })
        rec1 = rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 1,
            field2.column_name: 'Test record',
            field3.column_name: link_record
        })
        rec2 = rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 2,
            field2.column_name: 'Ánd again',
            field3.column_name: None,
        })
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'csv',
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content,
            b'id,name,linked: ID,linked: Name,auto uuid,auto id\r\n'
            b'1,Test record,1,Linked Display Name,%s,1\r\n'
            b'2,\xc3\x81nd again,,,%s,2\r\n' % (
                str(rec1.auto_uuid).encode(),
                str(rec2.auto_uuid).encode()
            )
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD
        )

    def test_reference_dataset_unknown_download(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(group=group, table_name='test_csv')
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            is_identifier=True
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'madeup',
            })
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(EventLog.objects.count(), log_count)


class TestSupportView(BaseTestCase):
    def test_create_support_request_invalid_email(self):
        response = self._authenticated_post(reverse('support'), {
            'email': 'x',
            'message': 'test message',
        })
        self.assertContains(response, 'Enter a valid email address')

    def test_create_support_request_invalid_message(self):
        response = self._authenticated_post(reverse('support'), {
            'email': 'noreply@example.com',
            'message': '',
        })
        self.assertContains(response, 'This field is required')

    @mock.patch('dataworkspace.apps.core.views.create_support_request')
    def test_create_support_request_no_attachments(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse('support'),
            data={
                'email': 'noreply@example.com',
                'message': 'A test message',
            },
            post_format='multipart'
        )
        self.assertContains(
            response,
            'Your request has been received. Your reference is: '
            '<strong>999</strong>.',
            html=True
        )
        mock_create_request.assert_called_once()

    @mock.patch('dataworkspace.apps.core.views.create_support_request')
    def test_create_support_request_with_attachments(self, mock_create_request):
        mock_create_request.return_value = 999
        fh = io.BytesIO()
        fh.write(b'This is some text')
        fh.seek(0)
        file1 = SimpleUploadedFile('file1.txt', fh.read(), content_type='text/plain')
        fh.seek(0)
        fh.write(b'This is some more text')
        fh.seek(0)
        file2 = SimpleUploadedFile('file2.txt', fh.read(), content_type='text/plain')
        response = self._authenticated_post(
            reverse('support'),
            data={
                'email': 'noreply@example.com',
                'message': 'A test message',
                'attachment1': file1,
                'attachment2': file2,
            },
            post_format='multipart'
        )
        self.assertContains(
            response,
            'Your request has been received. Your reference is: '
            '<strong>999</strong>.',
            html=True
        )
        mock_create_request.assert_called_once()


class TestSourceLinkDownloadView(BaseTestCase):
    def test_forbidden_dataset(self):
        group = factories.DataGroupingFactory.create()
        dataset = factories.DataSetFactory.create(
            grouping=group,
            published=True,
            user_access_type='REQUIRES_AUTHORIZATION',
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url='http://example.com'
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            reverse(
                'catalogue:dataset_source_link_download',
                kwargs={
                    'group_slug': group.slug,
                    'set_slug': dataset.slug,
                    'source_link_id': link.id
                }
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)

    def test_download_external_file(self):
        group = factories.DataGroupingFactory.create()
        dataset = factories.DataSetFactory.create(
            grouping=group,
            published=True,
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url='http://example.com'
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            reverse(
                'catalogue:dataset_source_link_download',
                kwargs={
                    'group_slug': group.slug,
                    'set_slug': dataset.slug,
                    'source_link_id': link.id
                }
            )
        )
        self.assertRedirects(response, 'http://example.com', fetch_redirect_response=False)
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        )

    @mock.patch('dataworkspace.apps.catalogue.views.boto3.client')
    def test_download_local_file(self, mock_client):
        group = factories.DataGroupingFactory.create()
        dataset = factories.DataSetFactory.create(
            grouping=group,
            published=True,
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        link = factories.SourceLinkFactory(
            id='158776ec-5c40-4c58-ba7c-a3425905ec45',
            dataset=dataset,
            link_type=SourceLink.TYPE_LOCAL,
            url='s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.txt'
        )
        log_count = EventLog.objects.count()
        mock_client().get_object.return_value = {
            'ContentType': 'text/plain',
            'Body': StreamingBody(
                io.BytesIO(b'This is a test file'),
                len(b'This is a test file')
            )
        }
        response = self._authenticated_get(
            reverse(
                'catalogue:dataset_source_link_download',
                kwargs={
                    'group_slug': group.slug,
                    'set_slug': dataset.slug,
                    'source_link_id': link.id
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.streaming_content)[0],
            b'This is a test file'
        )
        mock_client().get_object.assert_called_with(
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key=link.url
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        )


class TestSourceTableDownloadView(BaseTestCase):
    databases = ['default', 'my_database']

    def test_forbidden_dataset(self):
        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        source_table = factories.SourceTableFactory(
            dataset=dataset,
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            source_table.get_absolute_url()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)

    def test_missing_table(self):
        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(
                memorable_name='my_database',
            )
        )
        response = self._authenticated_get(
            source_table.get_absolute_url()
        )
        self.assertEqual(response.status_code, 404)

    def test_table_download(self):
        dsn = database_dsn(settings.DATABASES_DATA['my_database'])
        with connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE if not exists download_test (field2 int,field1 varchar(255));
                TRUNCATE TABLE download_test;
                INSERT INTO download_test VALUES(1, 'record1');
                INSERT INTO download_test VALUES(2, 'record2');
                '''
            )

        dataset = factories.DataSetFactory(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(
                memorable_name='my_database',
            ),
            schema='public',
            table='download_test',
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(source_table.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b''.join(response.streaming_content),
            b'field2,field1\r\n1,record1\r\n2,record2\r\nNumber of rows: 2\r\n'
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_SOURCE_TABLE_DOWNLOAD
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
            dataset=dataset,
            database=self.database,
            query=sql
        )

    def test_forbidden_dataset(self):
        dataset = factories.DataSetFactory(user_access_type='REQUIRES_AUTHORIZATION')
        source_table = factories.SourceTableFactory(
            dataset=dataset,
        )
        log_count = EventLog.objects.count()
        response = self._authenticated_get(
            source_table.get_absolute_url()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EventLog.objects.count(), log_count)

    def test_invalid_sql(self):
        query = self._create_query('SELECT * FROM table_that_does_not_exist;')
        self.assertRaises(
            Exception,
            lambda _: self._authenticated_get(query.get_absolute_url())
        )

    def test_dangerous_sql(self):
        # Test drop table
        query = self._create_query('DROP TABLE custom_query_test;')
        self.assertRaises(
            Exception,
            lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT to_regclass(\'custom_query_test\')')
            self.assertEqual(cursor.fetchone()[0], 'custom_query_test')

        # Test delete records
        query = self._create_query('DELETE FROM custom_query_test;')
        self.assertRaises(
            Exception,
            lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            self.assertEqual(cursor.fetchone()[0], 3)

        # Test update records
        query = self._create_query('UPDATE custom_query_test SET name=\'updated\';')
        self.assertRaises(
            Exception,
            lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test WHERE name=\'updated\'')
            self.assertEqual(cursor.fetchone()[0], 0)

        # Test insert record
        query = self._create_query('INSERT INTO custom_query_test (id, name) VALUES(4, \'added\')')
        self.assertRaises(
            Exception,
            lambda _: self._authenticated_get(query.get_absolute_url())
        )
        with connect(self.dsn) as conn, conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM custom_query_test')
            self.assertEqual(cursor.fetchone()[0], 3)

    def test_valid_sql(self):
        query = self._create_query('SELECT * FROM custom_query_test WHERE id IN (1, 3)')
        log_count = EventLog.objects.count()
        response = self._authenticated_get(query.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b''.join(response.streaming_content),
            b'id,name,date\r\n1,the first record,\r\n3,the last record,\r\nNumber of rows: 2\r\n'
        )
        self.assertEqual(EventLog.objects.count(), log_count + 1)
        self.assertEqual(
            EventLog.objects.latest().event_type,
            EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
        )
