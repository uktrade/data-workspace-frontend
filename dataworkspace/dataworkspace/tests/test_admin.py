import mock

from botocore.exceptions import ClientError

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dataworkspace.apps.datasets.models import (
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    ReferenceDatasetUploadLogRecord,
    ReferenceDatasetUploadLog
)
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseAdminTestCase


class TestReferenceDatasetAdmin(BaseAdminTestCase):
    databases = ['default', 'test_external_db']

    def test_create_reference_dataset_no_fields(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 0,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_no_identifiers(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 1,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-id': 1,
                'fields-0-reference_dataset': 1,
                'fields-0-name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_multiple_identifiers(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
                'fields-1-is_identifier': 'on',
            }
        )
        self.assertContains(response, 'Please select only one unique identifier field')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_duplicate_column_names(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-column_name': 'field',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(response, 'Please ensure column names are unique')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_duplicate_names(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field1',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(response, 'Please ensure field names are unique')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_column_name(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1 test',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field1',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(
            response,
            'Column names must start with a letter and contain only '
            'letters, numbers, underscores and full stops.'
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_existing_table_name(self):
        self._create_reference_dataset()
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create(name='test group')
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test_dataset',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(response, 'Reference dataset with this Table name already exists.')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_table_name(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create(name='test group')
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'test_dataset',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(
            response,
            'Table names must be prefixed with &quot;ref_&quot; '
            'and can contain only lowercase letters, numbers and underscores',
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_uppercase_table_name(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create(name='test group')
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_UPPERCASE',
                'slug': 'test-ref-1',
                'group': group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(
            response,
            'Table names must be prefixed with &quot;ref_&quot; '
            'and can contain only lowercase letters, numbers and underscores',
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_valid(self):
        num_datasets = ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create(name='test group')
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test ref 1',
                'table_name': 'ref_test_create_ref_dataset_valid',
                'slug': 'test-ref-1',
                'group': group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',
                'fields-1-name': 'field2',
                'fields-1-column_name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(response, 'was added successfully')
        self.assertEqual(num_datasets + 1, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-column_name': 'Added field 1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(response, 'Please select only one unique identifier field')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_display_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_display_name': 'on',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-column_name': 'Added field 1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(response, 'Please select only one display name field')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_column_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'duplicate',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'duplicate',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-column_name': 'added_field_1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(
            response,
            'Please ensure column names are unique'
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_invalid_column_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'a space',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-column_name': 'added_field_1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(
            response,
            'Column names must start with a letter and '
            'contain only letters, numbers, underscores and full stops.'
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_names(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
                'table_name': 'ref_test1',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field',
                'fields-0-column_name': 'updated_field1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field',
                'fields-1-column_name': 'updated_field2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-column_name': 'added_field_1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(response, 'Please ensure field names are unique')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_change_table_name(self):
        # Ensure that the table name cannot be changed via the admin
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            description='test',
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False,
            description='test',
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        original_table_name = reference_dataset.table_name
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': reference_dataset.name,
                'table_name': 'ref_test_updated',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': reference_dataset.short_description,
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': field1.name,
                'fields-0-column_name': field1.column_name,
                'fields-0-data_type': field1.data_type,
                'fields-0-description': field2.description,
                'fields-0-is_identifier': 'on',
                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': field2.name,
                'fields-1-column_name': field2.column_name,
                'fields-1-data_type': field2.data_type,
                'fields-1-description': field2.description,
                'fields-1-is_display_name': 'on',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())
        self.assertEqual(
            ReferenceDataset.objects.get(pk=reference_dataset.id).table_name,
            original_table_name,
        )

    def test_edit_reference_dataset_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'table_name': 'ref_test_updated',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'added_field_1',
                'fields-2-column_name': 'added_field_1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field 1',
                'fields-__prefix__-reference_dataset': reference_dataset.id,

                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields + 1, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_field(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
                'fields-1-DELETE': 'on',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_display_name_field(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False,
            is_display_name=True
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_display_name': 'on',
                'fields-1-DELETE': 'on',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the display name')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_all_fields(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',
                'fields-0-DELETE': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
                'fields-1-DELETE': 'on',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'table_name': reference_dataset.table_name,
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-DELETE': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-column_name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
                'fields-1-is_display_name': 'on',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields - 1, reference_dataset.fields.count())

    def test_reference_data_record_create_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='field2',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=False
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field1.column_name: 1,
            field2.column_name: 'record1',
        })
        num_records = len(reference_dataset.get_records())
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-add', args=(reference_dataset.id,)),
            {
                'reference_dataset': reference_dataset.id,
                field1.column_name: 1,
                field2.column_name: 'record2',
            }
        )
        self.assertContains(response, 'A record with this identifier already exists')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_create_missing_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='field2',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=False
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field1.column_name: 1,
            field2.column_name: 'record1',
        })
        num_records = len(reference_dataset.get_records())
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-add', args=(reference_dataset.id,)),
            {
                'reference_dataset': reference_dataset.id,
                field1.column_name: '',
                field2.column_name: 'record2',
            }
        )
        self.assertContains(response, 'This field is required')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_invalid_datatypes(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        url = reverse('dw-admin:reference-dataset-record-add', args=(reference_dataset.id,))
        num_records = len(reference_dataset.get_records())

        # Int
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a whole number.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Float
        field.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a number.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Date
        field.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid date.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Datetime
        field.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid date/time.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Time
        field.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid time.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_create(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='char',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='int',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name='float',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name='date',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name='time',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name='datetime',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name='bool',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_BOOLEAN,
        )
        num_records = len(reference_dataset.get_records())
        fields = {
            'reference_dataset': reference_dataset.id,
            field1.column_name: 'test1',
            field2.column_name: 1,
            field3.column_name: 2.0,
            field4.column_name: '2019-01-02',
            field5.column_name: '11:11:00',
            field6.column_name: '2019-05-25 14:30:59',
            field7.column_name: True,
        }
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-add', args=(reference_dataset.id,)),
            fields
        )
        self.assertContains(response, 'Reference dataset record added successfully')
        self.assertEqual(num_records + 1, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(1)
        del fields['reference_dataset']
        fields[field6.column_name] += '+00:00'
        for k, v in fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_edit_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='id',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field.column_name: 1
        })
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field.column_name: 2
        })
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records()[0]
        response = self._authenticated_post(
            reverse(
                'dw-admin:reference-dataset-record-edit', args=(reference_dataset.id, record.id)
            ),
            {
                'reference_dataset': reference_dataset.id,
                field.column_name: 2,
            }
        )
        self.assertContains(response, 'A record with this identifier already exists')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_edit_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='char',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='int',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name='float',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name='date',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name='time',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name='datetime',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name='bool',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_BOOLEAN,
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field1.column_name: 'test1',
            field2.column_name: 1,
            field3.column_name: 2.0,
            field4.column_name: '2019-01-02',
            field5.column_name: '11:11:00',
            field6.column_name: '2019-01-01 01:00:01',
            field7.column_name: True,
        })
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records().first()
        update_fields = {
            'reference_dataset': reference_dataset.id,
            field1.column_name: 'updated-char',
            field2.column_name: 99,
            field3.column_name: 1.0,
            field4.column_name: '2017-03-22',
            field5.column_name: '23:23:00',
            field6.column_name: '2019-05-25 14:30:59',
            field7.column_name: True,
        }
        response = self._authenticated_post(
            reverse(
                'dw-admin:reference-dataset-record-edit',
                args=(reference_dataset.id, record.id)
            ),
            update_fields
        )
        self.assertContains(response, 'Reference dataset record updated successfully')
        self.assertEqual(num_records, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(99)
        del update_fields['reference_dataset']
        update_fields[field6.column_name] += '+00:00'
        for k, v in update_fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_delete_confirm(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field.column_name: 1
        })
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records().first()
        response = self._authenticated_post(
            reverse(
                'dw-admin:reference-dataset-record-delete',
                args=(reference_dataset.id, record.id)
            ),
        )
        self.assertContains(
            response,
            'Are you sure you want to delete the record below from the reference data item'
        )
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_delete(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(None, {
            'reference_dataset': reference_dataset,
            field.column_name: 1
        })
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records()[0]
        response = self._authenticated_post(
            reverse(
                'dw-admin:reference-dataset-record-delete',
                args=(reference_dataset.id, record.id)
            ), {
                'id': record.id
            }
        )
        self.assertContains(
            response,
            'Reference dataset record deleted successfully'
        )
        self.assertEqual(num_records - 1, len(reference_dataset.get_records()))

    def test_create_circular_reference_dataset_link(self):
        reference_dataset = self._create_reference_dataset()
        self._create_reference_dataset(table_name='test_linked', slug='test-linked')
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'table_name': reference_dataset.table_name,
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': field1.name,
                'fields-0-column_name': field1.column_name,
                'fields-0-data_type': field1.data_type,
                'fields-0-is_identifier': 'on',

                'fields-1-id': '',
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'a name',
                'fields-1-column_name': 'a_column',
                'fields-1-data_type': ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                'fields-1-linked_reference_dataset': reference_dataset.id,
                'fields-1-description': 'a description',
            }
        )
        self.assertContains(
            response,
            'Select a valid choice. That choice is not one of the available choices.'
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_create_linked_field_as_foreign_key(self):
        reference_dataset = self._create_reference_dataset()
        linked_dataset = self._create_reference_dataset(
            table_name='test_linked',
            slug='test-linked'
        )
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            column_name='test'
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test updated',
                'table_name': reference_dataset.table_name,
                'slug': 'test-ref-1',
                'group': reference_dataset.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': field1.name,
                'fields-0-column_name': field1.column_name,
                'fields-0-data_type': field1.data_type,
                'fields-0-description': 'a description',

                'fields-1-id': '',
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'a name',
                'fields-1-column_name': 'a_column',
                'fields-1-data_type': ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                'fields-1-linked_reference_dataset': linked_dataset.id,
                'fields-1-description': 'a description',
                'fields-1-is_identifier': 'on',
            }
        )
        self.assertContains(
            response,
            'Identifier field cannot be linked reference data type'
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_linked_to_dataset_delete(self):
        # Do not allow deletion of a reference dataset if it is linked to by
        # one or more records within other datasets
        ref_ds1 = self._create_reference_dataset(table_name='test_change_linked_dataset1')
        ref_ds2 = self._create_reference_dataset(table_name='test_change_linked_dataset2')
        self._create_reference_dataset(table_name='test_change_linked_dataset3')
        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
            is_display_name=True
        )
        ReferenceDatasetField.objects.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset=ref_ds2,
        )

        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
            is_display_name=True
        )

        # Save a record in the linked to dataset
        record = ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2,
            'refid': 'test',
        })

        # Save a record in the linked from dataset (linking to the one above)
        ref_ds1.save_record(None, {
            'reference_dataset': ref_ds1,
            'refid': 'another_test',
            'link_id': record.id,
        })

        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_delete', args=(ref_ds2.id,)),
            {'id': ref_ds2.id}
        )
        self.assertContains(
            response,
            'Deleting the Reference dataset \'Test Group 1: Test Reference Dataset 1\' '
            'would require deleting the following protected related objects'
        )

    def test_delete_linked_to_reference_dataset_record(self):
        # Do not allow deletion of a reference dataset record if it is linked to by
        # one or more records within other datasets
        ref_ds1 = self._create_reference_dataset(table_name='test_change_linked_dataset1')
        ref_ds2 = self._create_reference_dataset(table_name='test_change_linked_dataset2')
        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset=ref_ds2,
            is_display_name=True
        )

        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
            is_display_name=True
        )

        # Save a record in the linked to dataset
        linked_to = ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2,
            'refid': 'test',
        })

        # Save a record in the linked from dataset (linking to the record above)
        linked_from = ref_ds1.save_record(None, {
            'reference_dataset': ref_ds1,
            'refid': 'another_test',
            'link_id': linked_to.id,
        })

        response = self._authenticated_post(
            reverse(
                'dw-admin:reference-dataset-record-delete',
                args=(ref_ds2.id, linked_to.id)
            ), {
                'id': linked_from.id
            }
        )
        self.assertContains(
            response,
            'The record below could not be deleted as it is linked to '
            'by other reference data records'
        )

    def test_change_linked_to_field_existing_records(self):
        # Ensure you can't edit linked reference dataset field if
        # there are already records linking to it
        ref_ds1 = self._create_reference_dataset(table_name='test_change_linked_dataset1')
        ref_ds2 = self._create_reference_dataset(table_name='test_change_linked_dataset2')
        ref_ds3 = self._create_reference_dataset(table_name='test_change_linked_dataset3')
        field1 = ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset=ref_ds2,
            is_display_name=True
        )

        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
            is_display_name=True
        )

        # Save a record in the linked to dataset
        linked_to = ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2,
            'refid': 'test',
        })

        # Save a record in the linked from dataset (linking to the one above)
        ref_ds1.save_record(None, {
            'reference_dataset': ref_ds1,
            'refid': 'another_test',
            'link_id': linked_to.id,
        })

        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(ref_ds1.id,)),
            {
                'id': ref_ds1.id,
                'name': 'test updated',
                'table_name': ref_ds1.table_name,
                'slug': 'test-ref-1',
                'group': ref_ds1.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': ref_ds1.id,
                'fields-0-name': field1.name,
                'fields-0-column_name': field1.column_name,
                'fields-0-data_type': field1.data_type,
                'fields-0-description': 'a description',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': ref_ds1.id,
                'fields-1-name': field2.name,
                'fields-1-column_name': field2.column_name,
                'fields-1-data_type': field2.data_type,
                'fields-1-linked_reference_dataset': ref_ds3.id,
                'fields-1-description': 'test',
                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(
            response,
            'Unable to change linked reference dataset when relations '
            'exist in this dataset'
        )

    def test_change_linked_reference_dataset(self):
        # If no records with links exist we should be able to edit the ref dataset link
        ref_ds1 = self._create_reference_dataset(table_name='test_change_linked_dataset1')
        ref_ds2 = self._create_reference_dataset(table_name='test_change_linked_dataset2')
        ref_ds3 = self._create_reference_dataset(table_name='test_change_linked_dataset3')
        field1 = ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset=ref_ds2,
            is_display_name=True
        )

        ReferenceDatasetField.objects.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
            is_display_name=True
        )

        # Save a record in the linked to dataset
        ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2,
            'refid': 'test',
        })

        # Save a record in the linked from dataset (linking to the one above)
        ref_ds1.save_record(None, {
            'reference_dataset': ref_ds1,
            'refid': 'another_test',
            'link_id': None,
        })

        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(ref_ds1.id,)),
            {
                'id': ref_ds1.id,
                'name': 'test updated',
                'table_name': ref_ds1.table_name,
                'slug': 'test-ref-1',
                'group': ref_ds1.group.id,
                'external_database': '',
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': ref_ds1.id,
                'fields-0-name': field1.name,
                'fields-0-column_name': field1.column_name,
                'fields-0-data_type': field1.data_type,
                'fields-0-description': 'a description',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': ref_ds1.id,
                'fields-1-name': field2.name,
                'fields-1-column_name': field2.column_name,
                'fields-1-data_type': field2.data_type,
                'fields-1-linked_reference_dataset': ref_ds3.id,
                'fields-1-description': 'test',
            }
        )
        self.assertContains(
            response,
            'The Reference dataset "<a href="/admin/datasets/referencedataset/{}/change/">'
            'Test Group 1: test updated</a>" was changed successfully.'.format(
                ref_ds1.id,
            ),
            html=True
        )

    def test_link_to_non_external_dataset(self):
        # Test that a dataset with external db cannot link to a dataset without one
        linked_to = factories.ReferenceDatasetFactory.create()
        factories.ReferenceDatasetFieldFactory.create(
            column_name='refid',
            reference_dataset=linked_to,
            data_type=1,
            is_identifier=True,
        )
        db = factories.DatabaseFactory.create()
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'test linked non-external',
                'table_name': 'ref_test_non_external_dataset_link',
                'slug': 'test-ref-link-non-external',
                'group': factories.DataGroupingFactory.create(name='test group').id,
                'external_database': db.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': ReferenceDatasetField.DATA_TYPE_CHAR,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',
                'fields-1-name': 'linked',
                'fields-1-column_name': 'linked',
                'fields-1-data_type': ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                'fields-1-description': 'Linked field',
                'fields-1-linked_reference_dataset': linked_to.id,
            }
        )
        self.assertContains(
            response,
            'Linked reference dataset does not exist on external database {}'.format(
                db.memorable_name
            )
        )

    def test_link_to_external_dataset(self):
        # Test that a dataset with external db can link to a dataset with one
        db = factories.DatabaseFactory.create()
        linked_to = factories.ReferenceDatasetFactory.create(
            name='linked to',
            table_name='ext_linked_to',
            external_database=db
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=linked_to,
            data_type=1,
            is_identifier=True,
        )
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_add'),
            {
                'name': 'linked from',
                'table_name': 'ref_test_non_external_dataset_link',
                'slug': 'test-ref-link-non-external',
                'group': factories.DataGroupingFactory.create(name='test group').id,
                'external_database': db.id,
                'short_description': 'test description that is short',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 0,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,
                'fields-0-name': 'field1',
                'fields-0-column_name': 'field1',
                'fields-0-data_type': ReferenceDatasetField.DATA_TYPE_CHAR,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',
                'fields-1-name': 'linked',
                'fields-1-column_name': 'linked',
                'fields-1-data_type': ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                'fields-1-description': 'Linked field',
                'fields-1-linked_reference_dataset': linked_to.id,
            }
        )
        self.assertContains(
            response,
            'The Reference dataset "<a href="/admin/datasets/referencedataset/{}/change/">'
            'test group: linked from</a>" was added successfully.'.format(
                ReferenceDataset.objects.last().id
            ),
            html=True
        )

    def test_reference_data_record_create_linked(self):
        to_link_ds = self._create_reference_dataset(table_name='to_link_ds')
        factories.ReferenceDatasetFieldFactory.create(
            column_name='identifier',
            reference_dataset=to_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True
        )
        to_link_record = to_link_ds.save_record(
            None, {'reference_dataset': to_link_ds, 'identifier': 'a'}
        )

        from_link_ds = self._create_reference_dataset(table_name='from_link_ds')
        factories.ReferenceDatasetFieldFactory.create(
            column_name='identifier',
            reference_dataset=from_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='link',
            reference_dataset=from_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset=to_link_ds
        )

        num_from_records = len(from_link_ds.get_records())
        num_to_records = len(to_link_ds.get_records())
        fields = {
            'reference_dataset': from_link_ds.id,
            'identifier': 'test',
            'link': to_link_record.id,
        }
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-add', args=(from_link_ds.id,)),
            fields
        )
        self.assertContains(response, 'Reference dataset record added successfully')
        self.assertEqual(num_from_records + 1, len(from_link_ds.get_records()))
        self.assertEqual(num_to_records, len(to_link_ds.get_records()))

    def test_reference_data_create_circular_link(self):
        # Create a dataset that links to a second dataset
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name='refds1',
            table_name='refds1',
        )
        ref_ds2 = factories.ReferenceDatasetFactory.create(
            name='refds2',
            table_name='refds2',
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset=ref_ds2
        )
        id_field = factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        # Edit second dataset to link to the first dataset
        response = self._authenticated_post(
            reverse('admin:datasets_referencedataset_change', args=(ref_ds2.id,)),
            {
                'id': ref_ds2.id,
                'name': ref_ds2.name,
                'table_name': ref_ds2.table_name,
                'slug': ref_ds2.slug,
                'group': ref_ds2.group.id,
                'external_database': '',
                'short_description': 'xxx',
                'description': '',
                'valid_from': '',
                'valid_to': '',
                'enquiries_contact': '',
                'licence': '',
                'restrictions_on_usage': '',
                'fields-TOTAL_FORMS': 2,
                'fields-INITIAL_FORMS': 1,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': id_field.id,
                'fields-0-reference_dataset': ref_ds2.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-column_name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',
                'fields-0-is_display_name': 'on',

                'fields-1-reference_dataset': ref_ds2.id,
                'fields-1-name': 'Added linked field',
                'fields-1-column_name': 'linked',
                'fields-1-data_type': ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                'fields-1-description': 'Linked field',
                'fields-1-linked_reference_dataset': ref_ds1.id,
            }
        )
        self.assertTrue(ref_ds2.fields.count(), 2)
        self.assertContains(response, 'Unable to link to a dataset that links to this dataset')

    def test_reference_dataset_upload_invalid_columns(self):
        # Create ref dataset
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name='ref_invalid_upload',
            table_name='ref_invalid_upload',
        )
        # Create 2 ref dataset fields
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='name',
            column_name='name',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_display_name=True,
        )

        # Create in memory file with 1 incorrect field name
        file1 = SimpleUploadedFile(
            'file1.csv',
            b'refid,invalid\r\nA1,test1\r\nA2,test2\r\n',
            content_type='text/csv'
        )

        # Assert upload fails with error message
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-upload', args=(ref_ds1.id,)),
            {'file': file1}
        )
        self.assertContains(
            response,
            'Please ensure the uploaded csv file headers match the target reference dataset columns'
        )

    def test_reference_dataset_upload_invalid_file_type(self):
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name='ref_invalid_upload',
            table_name='ref_invalid_upload',
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='name',
            column_name='name',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_display_name=True,
        )
        file1 = SimpleUploadedFile('file1.txt', b'some text\r\n', content_type='text/plain')
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-upload', args=(ref_ds1.id,)),
            {'file': file1}
        )
        self.assertContains(
            response,
            'File extension &#39;txt&#39; is not allowed.',
        )

    def test_reference_data_upload(self):
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name='ref_invalid_upload',
            table_name='ref_invalid_upload',
        )
        ref_ds2 = factories.ReferenceDatasetFactory.create(
            name='ref_invalid_upload2',
            table_name='ref_invalid_upload2',
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='name',
            column_name='name',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_display_name=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='link',
            column_name='link',
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset=ref_ds2,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='refid',
            column_name='refid',
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name='name',
            column_name='name',
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_display_name=True,
        )
        ref_ds1.increment_schema_version()
        ref_ds2.increment_schema_version()

        # Add records to the "linked to" table
        ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2, 'refid': 'A1', 'name': 'Linked to 1'
        })
        linked_to = ref_ds2.save_record(None, {
            'reference_dataset': ref_ds2, 'refid': 'A2', 'name': 'Linked to 2'
        })

        # Add some records to the "linked from" table
        existing_record = ref_ds1.save_record(None, {
            'reference_dataset': ref_ds1,
            'refid': 'B1',
            'name': 'Linked from 1',
            'link_id': linked_to.id
        })
        record_count = ref_ds1.get_records().count()

        upload_content = [
            b'refid,name,link',  # Header
            b'B1,Updated name,',  # Update existing record
            b'B2,New record 1,A2',  # Update existing record
            b'B3,New record 2,',  # Add record without link
            b'B4,Another record,Z1',  # Invalid link
        ]
        file1 = SimpleUploadedFile('file1.csv', b'\r\n'.join(upload_content), content_type='text/csv')
        response = self._authenticated_post(
            reverse('dw-admin:reference-dataset-record-upload', args=(ref_ds1.id,)),
            {'file': file1}
        )
        self.assertContains(
            response,
            'Reference dataset upload completed successfully',
        )
        self.assertContains(
            response,
            'Reference dataset upload completed successfully',
        )
        log_records = ReferenceDatasetUploadLog.objects.last().records.all()
        self.assertEqual(log_records.count(), 4)
        self.assertEqual(log_records[0].status, ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_UPDATED)
        self.assertEqual(log_records[1].status, ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED)
        self.assertEqual(log_records[2].status, ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED)
        self.assertEqual(log_records[3].status, ReferenceDatasetUploadLogRecord.STATUS_FAILURE)
        self.assertEqual(ref_ds1.get_records().count(), record_count + 2)

        # Check that the existing record was updated
        existing_record = ref_ds1.get_records().get(pk=existing_record.id)
        self.assertEqual(existing_record.name, 'Updated name')
        self.assertIsNone(existing_record.link)

        # Check new record with link was created
        new_record = ref_ds1.get_record_by_custom_id('B2')
        self.assertEqual(new_record.name, 'New record 1')
        self.assertIsNotNone(new_record.link)

        # Check new record without link was created
        new_record = ref_ds1.get_record_by_custom_id('B3')
        self.assertEqual(new_record.name, 'New record 2')
        self.assertIsNone(new_record.link)

        # Check record with invalid link was not created
        self.assertFalse(
            ref_ds1.get_records().filter(**{
                ref_ds1.identifier_field.column_name: 'B4'
            }).exists()
        )


class TestSourceLinkAdmin(BaseAdminTestCase):
    def test_source_link_upload_get(self):
        dataset = factories.DataSetFactory.create()
        response = self._authenticated_get(
            reverse('dw-admin:source-link-upload', args=(dataset.id,))
        )
        self.assertContains(response, 'Upload source link')

    @mock.patch('dataworkspace.apps.dw_admin.views.boto3.client')
    def test_source_link_upload_failure(self, mock_client):
        mock_client().put_object.side_effect = ClientError(
            error_response={'Error': {'Message': 'it failed'}},
            operation_name='put_object'
        )
        dataset = factories.DataSetFactory.create()
        link_count = dataset.sourcelink_set.count()
        file1 = SimpleUploadedFile('file1.txt', b'This is a test', content_type='text/plain')
        response = self._authenticated_post(
            reverse('dw-admin:source-link-upload', args=(dataset.id,)),
            {
                'dataset': dataset.id,
                'name': 'Test source link',
                'format': 'CSV',
                'frequency': 'Never',
                'file': file1,
            }
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(link_count, dataset.sourcelink_set.count())

    @mock.patch('dataworkspace.apps.dw_admin.views.boto3.client')
    def test_source_link_upload(self, mock_client):
        dataset = factories.DataSetFactory.create()
        link_count = dataset.sourcelink_set.count()
        file1 = SimpleUploadedFile('file1.txt', b'This is a test', content_type='text/plain')
        response = self._authenticated_post(
            reverse('dw-admin:source-link-upload', args=(dataset.id,)),
            {
                'dataset': dataset.id,
                'name': 'Test source link',
                'format': 'CSV',
                'frequency': 'Never',
                'file': file1,
            }
        )
        self.assertContains(response, 'Source link uploaded successfully')
        self.assertEqual(link_count + 1, dataset.sourcelink_set.count())
        link = dataset.sourcelink_set.latest('created_date')
        self.assertEqual(link.name, 'Test source link')
        self.assertEqual(link.format, 'CSV')
        self.assertEqual(link.frequency, 'Never')
        mock_client().put_object.assert_called_once_with(
            Body=mock.ANY,
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key=link.url
        )


class TestDatasetAdmin(BaseAdminTestCase):
    def test_delete_external_source_link(self):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=SourceLink.TYPE_EXTERNAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse('admin:datasets_dataset_change', args=(dataset.id,)),
            {
                'published': dataset.published,
                'name': dataset.name,
                'slug': dataset.slug,
                'short_description': 'test short description',
                'grouping': dataset.grouping.id,
                'description': 'test description',
                'volume': dataset.volume,
                'sourcelink_set-TOTAL_FORMS': '1',
                'sourcelink_set-INITIAL_FORMS': '1',
                'sourcelink_set-MIN_NUM_FORMS': '0',
                'sourcelink_set-MAX_NUM_FORMS': '1000',
                'sourcelink_set-0-id': source_link.id,
                'sourcelink_set-0-dataset': dataset.id,
                'sourcelink_set-0-name': 'test',
                'sourcelink_set-0-url': 'http://test.com',
                'sourcelink_set-0-format': 'test',
                'sourcelink_set-0-frequency': 'test',
                'sourcelink_set-0-DELETE': 'on',
                'sourcelink_set-__prefix__-id': '',
                'sourcelink_set-__prefix__-dataset': '571b8aac-7dc2-4e8b-bfae-73d5c25afd04',
                'sourcelink_set-__prefix__-name': '',
                'sourcelink_set-__prefix__-url': '',
                'sourcelink_set-__prefix__-format': '',
                'sourcelink_set-__prefix__-frequency': '',
                'sourcetable_set-TOTAL_FORMS': '0',
                'sourcetable_set-INITIAL_FORMS': '0',
                'sourcetable_set-MIN_NUM_FORMS': '0',
                'sourcetable_set-MAX_NUM_FORMS': '1000',
                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(dataset.sourcelink_set.count(), link_count - 1)

    @mock.patch('dataworkspace.apps.datasets.models.boto3.client')
    def test_delete_local_source_link_aws_failure(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=SourceLink.TYPE_LOCAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        mock_client.return_value.head_object.side_effect = ClientError(
            error_response={'Error': {'Message': 'it failed'}},
            operation_name='head_object'
        )
        response = self._authenticated_post(
            reverse('admin:datasets_dataset_change', args=(dataset.id,)),
            {
                'published': dataset.published,
                'name': dataset.name,
                'slug': dataset.slug,
                'short_description': 'test short description',
                'grouping': dataset.grouping.id,
                'description': 'test description',
                'volume': dataset.volume,
                'sourcelink_set-TOTAL_FORMS': '1',
                'sourcelink_set-INITIAL_FORMS': '1',
                'sourcelink_set-MIN_NUM_FORMS': '0',
                'sourcelink_set-MAX_NUM_FORMS': '1000',
                'sourcelink_set-0-id': source_link.id,
                'sourcelink_set-0-dataset': dataset.id,
                'sourcelink_set-0-name': 'test',
                'sourcelink_set-0-url': 'http://test.com',
                'sourcelink_set-0-format': 'test',
                'sourcelink_set-0-frequency': 'test',
                'sourcelink_set-0-DELETE': 'on',
                'sourcelink_set-__prefix__-id': '',
                'sourcelink_set-__prefix__-dataset': '571b8aac-7dc2-4e8b-bfae-73d5c25afd04',
                'sourcelink_set-__prefix__-name': '',
                'sourcelink_set-__prefix__-url': '',
                'sourcelink_set-__prefix__-format': '',
                'sourcelink_set-__prefix__-frequency': '',
                'sourcetable_set-TOTAL_FORMS': '0',
                'sourcetable_set-INITIAL_FORMS': '0',
                'sourcetable_set-MIN_NUM_FORMS': '0',
                'sourcetable_set-MAX_NUM_FORMS': '1000',
                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(response, 'Unable to access local file for deletion')
        self.assertEqual(dataset.sourcelink_set.count(), link_count)

    @mock.patch('dataworkspace.apps.datasets.models.boto3.client')
    def test_delete_local_source_link(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=SourceLink.TYPE_LOCAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse('admin:datasets_dataset_change', args=(dataset.id,)),
            {
                'published': dataset.published,
                'name': dataset.name,
                'slug': dataset.slug,
                'short_description': 'test short description',
                'grouping': dataset.grouping.id,
                'description': 'test description',
                'volume': dataset.volume,
                'sourcelink_set-TOTAL_FORMS': '1',
                'sourcelink_set-INITIAL_FORMS': '1',
                'sourcelink_set-MIN_NUM_FORMS': '0',
                'sourcelink_set-MAX_NUM_FORMS': '1000',
                'sourcelink_set-0-id': source_link.id,
                'sourcelink_set-0-dataset': dataset.id,
                'sourcelink_set-0-name': 'test',
                'sourcelink_set-0-url': 'http://test.com',
                'sourcelink_set-0-format': 'test',
                'sourcelink_set-0-frequency': 'test',
                'sourcelink_set-0-DELETE': 'on',
                'sourcelink_set-__prefix__-id': '',
                'sourcelink_set-__prefix__-dataset': '571b8aac-7dc2-4e8b-bfae-73d5c25afd04',
                'sourcelink_set-__prefix__-name': '',
                'sourcelink_set-__prefix__-url': '',
                'sourcelink_set-__prefix__-format': '',
                'sourcelink_set-__prefix__-frequency': '',
                'sourcetable_set-TOTAL_FORMS': '0',
                'sourcetable_set-INITIAL_FORMS': '0',
                'sourcetable_set-MIN_NUM_FORMS': '0',
                'sourcetable_set-MAX_NUM_FORMS': '1000',
                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(dataset.sourcelink_set.count(), link_count - 1)
        mock_client().delete_object.assert_called_once_with(
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key='http://test.com'
        )
