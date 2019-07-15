from django.urls import reverse

from app.tests import factories
from app.tests.common import BaseTestCase


class TestViews(BaseTestCase):
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

        ds1 = factories.DataSetFactory.create(grouping=group)
        ds2 = factories.DataSetFactory.create(grouping=group)
        ds3 = factories.DataSetFactory.create()

        rd1 = factories.ReferenceDatasetFactory(group=group)
        rd2 = factories.ReferenceDatasetFactory(group=group)
        rd3 = factories.ReferenceDatasetFactory()

        response = self._authenticated_get(
            reverse('datagroup_item', kwargs={'slug': group.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Ensure datasets in group are displayed
        self.assertContains(response, ds1.name, 1)
        self.assertContains(response, ds2.name, 1)

        # Ensure datasets not in group are not displayed
        self.assertNotContains(response, ds3.name)

        # Ensure reference datasets in group are displayed
        self.assertContains(response, rd1.name, 1)
        self.assertContains(response, rd2.name, 1)

        # Ensure reference datasets not in group are not displayed
        self.assertNotContains(response, rd3.name)

    def test_dataset_detail_view(self):
        group = factories.DataGroupingFactory.create()
        factories.DataSetFactory.create()
        ds = factories.DataSetFactory.create(grouping=group)
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
            is_identifier=True
        )
        response = self._authenticated_get(
            reverse('reference_dataset_download', kwargs={
                'group_slug': group.slug,
                'reference_slug': rds.slug,
                'format': 'json',
            })
        )
        self.assertEqual(response.status_code, 200)

    def test_reference_dataset_csv_download(self):
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
                'format': 'csv',
            })
        )
        self.assertEqual(response.status_code, 200)

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
