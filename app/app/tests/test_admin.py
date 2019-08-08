import mock
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from app import models
from app.tests import factories
from app.tests.common import BaseAdminTestCase


class TestReferenceDatasetAdmin(BaseAdminTestCase):
    def test_create_reference_dataset_no_fields(self):
        num_datasets = models.ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_add'),
            {
                'name': 'test ref 1',
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
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())

    def test_create_reference_dataset_no_identifiers(self):
        num_datasets = models.ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_add'),
            {
                'name': 'test ref 1',
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
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())

    def test_create_reference_dataset_multiple_identifiers(self):
        num_datasets = models.ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_add'),
            {
                'name': 'test ref 1',
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
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())

    def test_create_reference_dataset_valid(self):
        num_datasets = models.ReferenceDataset.objects.count()
        group = factories.DataGroupingFactory.create(name='test group')
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_add'),
            {
                'name': 'test ref 1',
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
                'fields-0-data_type': 2,
                'fields-0-description': 'A field',
                'fields-0-is_identifier': 'on',
                'fields-1-name': 'field2',
                'fields-1-data_type': 1,
                'fields-1-description': 'Another field',
            }
        )
        self.assertContains(response, 'was added successfully')
        self.assertEqual(num_datasets + 1, models.ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_identifier(self):
        reference_dataset = factories.ReferenceDatasetFactory()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=2,
        )
        num_datasets = models.ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_change', args=(reference_dataset.id,)),
            {
                'id': reference_dataset.id,
                'name': 'test ref 1',
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
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-is_identifier': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'Added field 1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field',
            }
        )
        self.assertContains(response, 'Please select only one unique identifier field')
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())

    def test_edit_reference_dataset_valid(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
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
        num_datasets = models.ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_change', args=(reference_dataset.id,)),
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
                'fields-TOTAL_FORMS': 3,
                'fields-INITIAL_FORMS': 2,
                'fields-MIN_NUM_FORMS': 1,
                'fields-MAX_NUM_FORMS': 1000,

                'fields-0-id': field1.id,
                'fields-0-reference_dataset': reference_dataset.id,
                'fields-0-name': 'updated_field_1',
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',

                'fields-2-reference_dataset': reference_dataset.id,
                'fields-2-name': 'added_field_1',
                'fields-2-data_type': 3,
                'fields-2-description': 'Added field 1',
                'fields-__prefix__-reference_dataset': reference_dataset.id,
                '_continue': 'Save and continue editing',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())
        self.assertEqual(num_fields + 1, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_field(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
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
        num_datasets = models.ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_change', args=(reference_dataset.id,)),
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
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
                'fields-1-DELETE': 'on',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_all_fields(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
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
        num_datasets = models.ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_change', args=(reference_dataset.id,)),
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
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-DELETE': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
                'fields-1-DELETE': 'on',
            }
        )
        self.assertContains(response, 'Please ensure one field is set as the unique identifier')
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_valid(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
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
        num_datasets = models.ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse('admin:app_referencedataset_change', args=(reference_dataset.id,)),
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
                'fields-0-data_type': 2,
                'fields-0-description': 'Updated field 1',
                'fields-0-DELETE': 'on',

                'fields-1-id': field2.id,
                'fields-1-reference_dataset': reference_dataset.id,
                'fields-1-name': 'updated_field_2',
                'fields-1-data_type': 2,
                'fields-1-description': 'Updated field 2',
                'fields-1-is_identifier': 'on',
            }
        )
        self.assertContains(response, 'was changed successfully')
        self.assertEqual(num_datasets, models.ReferenceDataset.objects.count())
        self.assertEqual(num_fields - 1, reference_dataset.fields.count())

    def test_reference_data_record_create_duplicate_identifier(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='field2',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_CHAR,
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
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='field2',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_CHAR,
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
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        url = reverse('dw-admin:reference-dataset-record-add', args=(reference_dataset.id,))
        num_records = len(reference_dataset.get_records())

        # Int
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a whole number.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Float
        field.data_type = models.ReferenceDatasetField.DATA_TYPE_FLOAT
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a number.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Date
        field.data_type = models.ReferenceDatasetField.DATA_TYPE_DATE
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid date.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Datetime
        field.data_type = models.ReferenceDatasetField.DATA_TYPE_DATETIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid date/time.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Time
        field.data_type = models.ReferenceDatasetField.DATA_TYPE_TIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: 'a string'})
        self.assertContains(response, 'Enter a valid time.')
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_create(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='char',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='int',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name='float',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name='date',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name='time',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name='datetime',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name='bool',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_BOOLEAN,
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
        self.assertContains(response, 'Reference data set record added successfully')
        self.assertEqual(num_records + 1, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(1)
        del fields['reference_dataset']
        fields[field6.column_name] += '+00:00'
        for k, v in fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_edit_duplicate_identifier(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='id',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
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
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name='char',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name='int',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name='float',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name='date',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name='time',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name='datetime',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name='bool',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_BOOLEAN,
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
        self.assertContains(response, 'Reference data set record updated successfully')
        self.assertEqual(num_records, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(99)
        del update_fields['reference_dataset']
        update_fields[field6.column_name] += '+00:00'
        for k, v in update_fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_delete_confirm(self):
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
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
        reference_dataset = factories.ReferenceDatasetFactory.create()
        field = factories.ReferenceDatasetFieldFactory.create(
            name='field1',
            reference_dataset=reference_dataset,
            data_type=models.ReferenceDatasetField.DATA_TYPE_INT,
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
            'Reference data set record deleted successfully'
        )
        self.assertEqual(num_records - 1, len(reference_dataset.get_records()))


class TestSourceLinkAdmin(BaseAdminTestCase):
    def test_source_link_upload_get(self):
        dataset = factories.DataSetFactory.create()
        response = self._authenticated_get(
            reverse('dw-admin:source-link-upload', args=(dataset.id,))
        )
        self.assertContains(response, 'Upload source link')

    @mock.patch('app.dw_admin.views.boto3.client')
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

    @mock.patch('app.dw_admin.views.boto3.client')
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
            link_type=models.SourceLink.TYPE_EXTERNAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse('admin:app_dataset_change', args=(dataset.id,)),
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

    @mock.patch('app.models.boto3.client')
    def test_delete_local_source_link_aws_failure(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=models.SourceLink.TYPE_LOCAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        mock_client.return_value.head_object.side_effect = ClientError(
            error_response={'Error': {'Message': 'it failed'}},
            operation_name='head_object'
        )
        response = self._authenticated_post(
            reverse('admin:app_dataset_change', args=(dataset.id,)),
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

    @mock.patch('app.models.boto3.client')
    def test_delete_local_source_link(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=models.SourceLink.TYPE_LOCAL,
            dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse('admin:app_dataset_change', args=(dataset.id,)),
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
