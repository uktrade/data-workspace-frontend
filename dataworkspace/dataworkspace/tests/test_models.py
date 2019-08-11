import mock
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection

from dataworkspace.apps.datasets.models import DataGrouping, ReferenceDataset, ReferenceDatasetField, SourceLink
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase


class TestModels(BaseTestCase):
    @staticmethod
    def _create_reference_dataset():
        group = DataGrouping.objects.create(
            name='Test Group 1',
            short_description='Testing...',
        )
        ref_dataset = ReferenceDataset.objects.create(
            group=group,
            name='Test Reference Dataset 1',
            short_description='Testing...'
        )
        return ref_dataset

    @staticmethod
    def _table_exists(table_name: str):
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)', [table_name])
            return cursor.fetchone()[0] == table_name

    @staticmethod
    def _get_column_data(table_name: str, column_name: str):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT *
                FROM information_schema.columns
                WHERE table_name=%s
                AND column_name=%s
                ''', [
                    table_name,
                    column_name
                ]
            )
            columns = [col[0] for col in cursor.description]
            record = cursor.fetchone()
            if record is not None:
                return dict(zip(columns, record))
            return None

    def test_create_reference_dataset(self):
        ref_dataset = self._create_reference_dataset()

        # Ensure database table name is correct
        self.assertEqual(
            ref_dataset.table_name,
            'refdata__{}'.format(ref_dataset.id)
        )

        # Ensure the table was created in the db
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.schema_version, 0)

    def test_delete_reference_dataset(self):
        # Ensure the table is _not_ removed when the reference dataset is (soft) deleted
        ref_dataset = self._create_reference_dataset()
        schema_version = ref_dataset.schema_version
        ref_dataset.delete()
        ref_dataset = ReferenceDataset.objects.get(id=ref_dataset.id)
        self.assertTrue(ref_dataset.deleted)
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.schema_version, schema_version)

    def _create_and_validate_field(self, ref_dataset: ReferenceDatasetField,
                                   field_name: str, field_type: str):
        major_version = ref_dataset.major_version
        schema_version = ref_dataset.schema_version
        rdf = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name=field_name,
            data_type=field_type
        )
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertIsNotNone(column)
        self.assertEqual(column['column_name'], rdf.column_name)
        self.assertEqual(ref_dataset.major_version, major_version)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)
        return rdf

    def test_create_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset()

        # Character field
        self._create_and_validate_field(
            ref_dataset,
            'char_field',
            ReferenceDatasetField.DATA_TYPE_CHAR
        )

        # Integer field
        self._create_and_validate_field(
            ref_dataset,
            'int_field',
            ReferenceDatasetField.DATA_TYPE_INT
        )

        # Float field
        self._create_and_validate_field(
            ref_dataset,
            'float_field',
            ReferenceDatasetField.DATA_TYPE_FLOAT
        )

        # Date field
        self._create_and_validate_field(
            ref_dataset,
            'date_field',
            ReferenceDatasetField.DATA_TYPE_DATE
        )

        # Time field
        self._create_and_validate_field(
            ref_dataset,
            'time_field',
            ReferenceDatasetField.DATA_TYPE_TIME
        )

        # Datetime field
        self._create_and_validate_field(
            ref_dataset,
            'datetime_field',
            ReferenceDatasetField.DATA_TYPE_DATETIME
        )

        # Boolean field
        self._create_and_validate_field(
            ref_dataset,
            'boolean_field',
            ReferenceDatasetField.DATA_TYPE_BOOLEAN
        )

    def test_edit_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset()

        # Change column name - should not affect the db column
        rdf = self._create_and_validate_field(
            ref_dataset,
            'char_field',
            ReferenceDatasetField.DATA_TYPE_CHAR
        )
        rdf.name = 'updated_field'
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertIsNotNone(column)
        self.assertEqual(column['column_name'], rdf.column_name)

        # Change data type

        # Char -> Int
        rdf = self._create_and_validate_field(
            ref_dataset,
            'test_field',
            ReferenceDatasetField.DATA_TYPE_CHAR
        )
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_INT
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'int4')

        # Int -> Float
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'float8')

        # Float -> Date
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'date')

        # Date -> Time
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'time')

        # Time -> Datetime
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'timestamp')

        # Datetime -> Bool
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_BOOLEAN
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['udt_name'], 'bool')

    def test_delete_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset()
        field = self._create_and_validate_field(
            ref_dataset,
            'test_field',
            ReferenceDatasetField.DATA_TYPE_CHAR
        )
        self.assertEqual(ref_dataset.major_version, 1)
        schema_version = ref_dataset.schema_version
        field.delete()
        column = self._get_column_data(ref_dataset.table_name, 'test_field')
        self.assertIsNone(column)
        self.assertEqual(ref_dataset.major_version, 2)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)

    def test_add_record(self):
        ref_dataset = self._create_reference_dataset()
        minor_version = ref_dataset.minor_version
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        record = ref_dataset.get_record_by_custom_id(1)
        self.assertIsNotNone(record)
        record = ref_dataset.get_record_by_internal_id(record.id)
        self.assertIsNotNone(record)
        self.assertEqual(ref_dataset.minor_version, minor_version + 1)

    def test_edit_record(self):
        ref_dataset = self._create_reference_dataset()
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        self.assertEqual(ref_dataset.major_version, 1)
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 1)
        record = ref_dataset.get_record_by_custom_id(1)
        ref_dataset.save_record(record.id, {
            'reference_dataset': ref_dataset,
            field1.column_name: 999,
            field2.column_name: 'changed'
        })
        self.assertRaises(
            ObjectDoesNotExist,
            ref_dataset.get_record_by_custom_id,
            1
        )
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 2)
        self.assertIsNotNone(ref_dataset.get_record_by_custom_id(999))

    def test_delete_record(self):
        ref_dataset = self._create_reference_dataset()
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 0)
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 1)
        record = ref_dataset.get_record_by_custom_id(1)
        ref_dataset.delete_record(record.id)
        self.assertRaises(
            ObjectDoesNotExist,
            ref_dataset.get_record_by_custom_id,
            1
        )
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 2)


class TestSourceLinkModel(BaseTestCase):
    @mock.patch('dataworkspace.apps.datasets.models.boto3.client')
    def test_delete_local_source_link(self, mock_client):
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
        link.delete()
        self.assertFalse(
            SourceLink.objects.filter(id='158776ec-5c40-4c58-ba7c-a3425905ec45').exists()
        )
        mock_client.assert_called_once()
        mock_client().delete_object.assert_called_once_with(
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key=link.url
        )

    @mock.patch('dataworkspace.apps.datasets.models.boto3.client')
    def test_delete_external_source_link(self, mock_client):
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
        link.delete()
        self.assertFalse(
            SourceLink.objects.filter(id='158776ec-5c40-4c58-ba7c-a3425905ec45').exists()
        )
        mock_client.assert_not_called()
