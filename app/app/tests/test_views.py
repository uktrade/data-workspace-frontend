import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import mock

from app.tests import factories
from app.tests.common import BaseTestCase


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
        response = self._authenticated_get(reverse('root'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, g1.name, 1)
        self.assertContains(response, g2.name, 1)

    def test_group_detail_view(self):
        group = factories.DataGroupingFactory.create()

        ds1 = factories.DataSetFactory.create(grouping=group, published=True)
        ds2 = factories.DataSetFactory.create(grouping=group, published=False)
        ds3 = factories.DataSetFactory.create()

        factories.ReferenceDatasetFactory(group=group)
        factories.ReferenceDatasetFactory(group=group)
        factories.ReferenceDatasetFactory()

        response = self._authenticated_get(
            reverse('datagroup_item', kwargs={'slug': group.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Ensure datasets in group are displayed
        self.assertContains(response, ds1.name, 1)

        # Ensure unpublished datasets are not displayed
        self.assertContains(response, ds2.name, 0)

        # Ensure datasets not in group are not displayed
        self.assertNotContains(response, ds3.name)

    def test_dataset_detail_view_unpublished(self):
        group = factories.DataGroupingFactory.create()
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(grouping=group)
        factories.SourceLinkFactory(dataset=ds)
        factories.SourceLinkFactory(dataset=ds)
        response = self._authenticated_get(
            reverse('dataset_fullpath', kwargs={
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
            reverse('dataset_fullpath', kwargs={
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
            reverse('reference_dataset', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, rds.name)

    def test_reference_dataset_json_download(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(group=group)
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='name',
            data_type=1,
        )
        rds.save_record(None, {'id': 1, 'name': 'Test recórd'})
        rds.save_record(None, {'id': 2, 'name': 'Ánd again'})
        response = self._authenticated_get(
            reverse('reference_dataset_download', kwargs={
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
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='id',
            data_type=2,
            is_identifier=True
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name='name',
            data_type=1,
        )
        rds.save_record(None, {'id': 1, 'name': 'Test recórd'})
        rds.save_record(None, {'id': 2, 'name': 'Ánd again'})
        response = self._authenticated_get(
            reverse('reference_dataset_download', kwargs={
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
            reverse('reference_dataset_download', kwargs={
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

    @mock.patch('app.views_general.create_support_request')
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

    @mock.patch('app.views_general.create_support_request')
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
