import io
import mock

from botocore.response import StreamingBody

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


from dataworkspace.apps.datasets.models import SourceLink
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

        rds1 = factories.ReferenceDatasetFactory(group=group, published=True)
        rds2 = factories.ReferenceDatasetFactory(group=group, published=False)
        rds3 = factories.ReferenceDatasetFactory()
        rds4 = factories.ReferenceDatasetFactory(group=group, published=False)
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
        rds = factories.ReferenceDatasetFactory.create(group=group)
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
        rds = factories.ReferenceDatasetFactory.create(group=group)
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
        rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 1,
            field2.column_name: 'Test recórd'
        })
        rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 2,
            field2.column_name: 'Ánd again'
        })
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'json',
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            'id': 1, 'name': 'Test recórd'
        }, {
            'id': 2, 'name': 'Ánd again'
        }])

    def test_reference_dataset_csv_download(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(group=group)
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
        rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 1,
            field2.column_name: 'Test recórd'
        })
        rds.save_record(None, {
            'reference_dataset': rds,
            field1.column_name: 2,
            field2.column_name: 'Ánd again'
        })
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
            b'id,name\r\n1,Test rec\xc3\xb3rd\r\n2,\xc3\x81nd again\r\n'
        )

    def test_reference_dataset_unknown_download(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(group=group)
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            is_identifier=True
        )
        response = self._authenticated_get(
            reverse('catalogue:reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'madeup',
            })
        )
        self.assertEqual(response.status_code, 404)


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
