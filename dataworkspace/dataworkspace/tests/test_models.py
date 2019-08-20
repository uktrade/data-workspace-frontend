import mock
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, connections

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.datasets.models import DataGrouping, ReferenceDataset, \
    ReferenceDatasetField, SourceLink
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase


class BaseModelsTests(BaseTestCase):
    @staticmethod
    def _table_exists(table_name: str, database=None):
        if database is not None:
            with connections[database].cursor() as cursor:
                cursor.execute('SELECT to_regclass(%s)', [table_name])
                return cursor.fetchone()[0] == table_name
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)', [table_name])
            return cursor.fetchone()[0] == table_name

    def _create_and_validate_field(self, ref_dataset: ReferenceDatasetField,
                                   field_name: str, field_type: str, database='default'):
        major_version = ref_dataset.major_version
        schema_version = ref_dataset.schema_version
        rdf = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name=field_name,
            column_name=field_name,
            data_type=field_type
        )
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name, database=database)
        self.assertIsNotNone(column)
        self.assertEqual(column['column_name'], rdf.column_name)
        self.assertEqual(ref_dataset.major_version, major_version)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)
        return rdf

    @staticmethod
    def _get_column_data(table_name: str, column_name: str, database='default'):
        with connections[database].cursor() as cursor:
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


class TestModels(BaseModelsTests):
    def test_create_reference_dataset(self):
        ref_dataset = self._create_reference_dataset()
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.schema_version, 0)

    def test_edit_reference_dataset_table_name(self):
        ref_dataset = self._create_reference_dataset()
        ref_dataset.table_name = 'ref_new_table_name'
        ref_dataset.save()

        # Ensure the table was created in the db
        self.assertFalse(self._table_exists('ref_test_dataset'))
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.schema_version, 1)

    def test_delete_reference_dataset(self):
        # Ensure the table is _not_ removed when the reference dataset is (soft) deleted
        ref_dataset = self._create_reference_dataset()
        schema_version = ref_dataset.schema_version
        ref_dataset.delete()
        ref_dataset = ReferenceDataset.objects.get(id=ref_dataset.id)
        self.assertTrue(ref_dataset.deleted)
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.schema_version, schema_version)

    def test_create_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset(table_name='testing')

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
        ref_dataset = self._create_reference_dataset(table_name='test_edit_reference_dataset_field')

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

        # Ensure name change is reflected in the db
        rdf.column_name = 'updated'
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column['column_name'], rdf.column_name)

    def test_delete_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset(
            table_name='test_delete_reference_dataset_field'
        )
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
        ref_dataset = self._create_reference_dataset(table_name='test_add_record')
        minor_version = ref_dataset.minor_version
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
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
        ref_dataset = self._create_reference_dataset(table_name='test_edit_record')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
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
        ref_dataset = self._create_reference_dataset(table_name='test_delete_record')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
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


class TestExternalModels(BaseModelsTests):
    databases = ['default', 'test_external_db', 'test_external_db2']

    def _create_reference_dataset(self, **kwargs):
        return super()._create_reference_dataset(
            external_database=factories.DatabaseFactory.create(),
            **kwargs)

    @staticmethod
    def _record_exists(table_name, identifier_field, record_id, database='test_external_db'):
        with connections[database].cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM {} WHERE {}=%s'.format(
                table_name,
                identifier_field,
            ), [record_id])
            return cursor.fetchone()[0] == 1

    def test_create_reference_dataset_external(self):
        ref_dataset = self._create_reference_dataset()
        self.assertTrue(self._table_exists(ref_dataset.table_name, database='test_external_db'))

    def test_edit_reference_dataset_table_name_external(self):
        ref_dataset = self._create_reference_dataset(table_name='test_edit_table')
        self.assertTrue(self._table_exists('test_edit_table', database='test_external_db'))
        ref_dataset.table_name = 'new_table_name'
        ref_dataset.save()
        self.assertFalse(self._table_exists('test_edit_table', database='test_external_db'))
        self.assertTrue(self._table_exists('new_table_name', database='test_external_db'))

    def test_delete_reference_dataset_external(self):
        # Ensure external tables are removed when the reference dataset deleted
        ref_dataset = self._create_reference_dataset(table_name='test_del_external')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        self.assertTrue(self._table_exists(ref_dataset.table_name, database='test_external_db'))
        ref_dataset.delete()
        self.assertFalse(self._table_exists(ref_dataset.table_name, database='test_external_db'))

    def test_create_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(table_name='thisisatest')

        # Character field
        self._create_and_validate_field(
            ref_dataset,
            'char_field',
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database='test_external_db'
        )

        # Integer field
        self._create_and_validate_field(
            ref_dataset,
            'int_field',
            ReferenceDatasetField.DATA_TYPE_INT,
            database='test_external_db'
        )

        # Float field
        self._create_and_validate_field(
            ref_dataset,
            'float_field',
            ReferenceDatasetField.DATA_TYPE_FLOAT,
            database='test_external_db'
        )

        # Date field
        self._create_and_validate_field(
            ref_dataset,
            'date_field',
            ReferenceDatasetField.DATA_TYPE_DATE,
            database='test_external_db'
        )

        # Time field
        self._create_and_validate_field(
            ref_dataset,
            'time_field',
            ReferenceDatasetField.DATA_TYPE_TIME,
            database='test_external_db'
        )

        # Datetime field
        self._create_and_validate_field(
            ref_dataset,
            'datetime_field',
            ReferenceDatasetField.DATA_TYPE_DATETIME,
            database='test_external_db'
        )

        # Boolean field
        self._create_and_validate_field(
            ref_dataset,
            'boolean_field',
            ReferenceDatasetField.DATA_TYPE_BOOLEAN,
            database='test_external_db'
        )

    def test_edit_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(
            table_name='test_edit_reference_dataset_field'
        )

        # Change column name - should not affect the db column
        rdf = self._create_and_validate_field(
            ref_dataset,
            'char_field',
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database='test_external_db'
        )
        rdf.name = 'updated_field'
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertIsNotNone(column)
        self.assertEqual(column['column_name'], rdf.column_name)

        # Change data type

        # Char -> Int
        rdf = self._create_and_validate_field(
            ref_dataset,
            'test_field',
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database='test_external_db'
        )
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_INT
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'int4')

        # Int -> Float
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'float8')

        # Float -> Date
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'date')

        # Date -> Time
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'time')

        # Time -> Datetime
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'timestamp')

        # Datetime -> Bool
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_BOOLEAN
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['udt_name'], 'bool')

        # Ensure name change is reflected in the db
        rdf.column_name = 'updated'
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name,
            rdf.column_name,
            database='test_external_db'
        )
        self.assertEqual(column['column_name'], rdf.column_name)

    def test_delete_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(table_name='test_delete_field')
        field = self._create_and_validate_field(
            ref_dataset,
            'test_field',
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database='test_external_db'
        )
        schema_version = ref_dataset.schema_version
        field.delete()
        column = self._get_column_data(
            ref_dataset.table_name,
            'test_field',
            database='test_external_db'
        )
        self.assertIsNone(column)
        self.assertEqual(ref_dataset.major_version, 2)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)

    def test_add_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name='test_add_record')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        self.assertTrue(self._record_exists('test_add_record', 'field1', 1))

    def test_edit_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name='test_edit_record')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        self.assertEqual(ref_dataset.major_version, 1)
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        self.assertTrue(self._record_exists('test_edit_record', 'field1', 1))

    def test_delete_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name='test_delete_record')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'testing...'
        })
        record = ref_dataset.get_record_by_custom_id(1)
        ref_dataset.delete_record(record.id)
        self.assertFalse(self._record_exists('test_delete_record', 'field1', 1))

    def test_create_external_database(self):
        # Ensure existing records are synced to any new database on creation
        group = DataGrouping.objects.create(
            name='Test Group 1',
            slug='test-group-1',
            short_description='Testing...',
        )
        ref_dataset = ReferenceDataset.objects.create(
            group=group,
            name='Test Reference Dataset 1',
            table_name='ext_db_test',
            short_description='Testing...',
            slug='test-reference-dataset-1',
            published=True,
            external_database=factories.DatabaseFactory.create(),
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
        })
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 2,
        })
        self.assertTrue(self._record_exists('ext_db_test', 'field1', 1))
        self.assertTrue(self._record_exists('ext_db_test', 'field1', 2))

    def test_edit_add_external_database(self):
        group = DataGrouping.objects.create(
            name='Test Group 1',
            slug='test-group-1',
            short_description='Testing...',
        )
        ref_dataset = ReferenceDataset.objects.create(
            group=group,
            name='Test Reference Dataset 1',
            table_name='ext_db_edit_test',
            short_description='Testing...',
            slug='test-reference-dataset-1',
            published=True,
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
        })
        ref_dataset.external_database = Database.objects.get_or_create(
            memorable_name='test_external_db2'
        )[0]
        ref_dataset.save()

        self.assertFalse(
            self._table_exists(ref_dataset.table_name, database='test_external_db')
        )
        self.assertTrue(
            self._table_exists(ref_dataset.table_name, database='test_external_db2')
        )
        self.assertTrue(
            self._record_exists('ext_db_edit_test', 'field1', 1, database='test_external_db2')
        )

    def test_edit_change_external_database(self):
        group = DataGrouping.objects.create(
            name='Test Group 1',
            slug='test-group-1',
            short_description='Testing...',
        )
        ref_dataset = ReferenceDataset.objects.create(
            group=group,
            name='Test Reference Dataset 1',
            table_name='ext_db_change_test',
            short_description='Testing...',
            slug='test-reference-dataset-1',
            published=True,
            external_database=factories.DatabaseFactory.create()
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
        })
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 2,
        })
        self.assertTrue(
            self._table_exists(ref_dataset.table_name, database='test_external_db')
        )
        ref_dataset.external_database = factories.DatabaseFactory.create(
            memorable_name='test_external_db2'
        )
        # raise Exception(ref_dataset.external_database)
        ref_dataset.save()
        self.assertFalse(
            self._table_exists(ref_dataset.table_name, database='test_external_db')
        )
        self.assertTrue(
            self._table_exists(ref_dataset.table_name, database='test_external_db2')
        )
        self.assertTrue(
            self._record_exists('ext_db_change_test', 'field1', 1, database='test_external_db2')
        )
        self.assertTrue(
            self._record_exists('ext_db_change_test', 'field1', 2, database='test_external_db2')
        )

    def test_edit_remove_external_database(self):
        group = DataGrouping.objects.create(
            name='Test Group 1',
            slug='test-group-1',
            short_description='Testing...',
        )
        ref_dataset = ReferenceDataset.objects.create(
            group=group,
            name='Test Reference Dataset 1',
            table_name='ext_db_delete_test',
            short_description='Testing...',
            slug='test-reference-dataset-1',
            published=True,
            external_database=factories.DatabaseFactory.create()
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
        })
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 2,
        })
        self.assertTrue(
            self._table_exists(ref_dataset.table_name, database='test_external_db')
        )
        ref_dataset.external_database = None
        ref_dataset.save()
        self.assertFalse(
            self._table_exists(ref_dataset.table_name, database='test_external_db')
        )

    def test_external_database_full_sync(self):
        ref_dataset = self._create_reference_dataset(table_name='test_full_sync')
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field1',
            column_name='field1',
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name='field2',
            column_name='field2',
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 1,
            field2.column_name: 'record 1'
        })
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 2,
            field2.column_name: 'record 2'
        })
        ref_dataset.save_record(None, {
            'reference_dataset': ref_dataset,
            field1.column_name: 3,
            field2.column_name: 'record 3'
        })
        # Sync with ext db
        ref_dataset.sync_to_external_database('test_external_db')
        # Check that the records exist in ext db
        self.assertTrue(self._record_exists('test_full_sync', 'field1', 1))
        self.assertTrue(self._record_exists('test_full_sync', 'field1', 2))
        self.assertTrue(self._record_exists('test_full_sync', 'field1', 3))
        # Delete a record
        ref_dataset.get_records().last().delete()
        # Sync with ext db
        ref_dataset.sync_to_external_database('test_external_db')
        # Ensure record was deleted externally
        self.assertTrue(self._record_exists('test_full_sync', 'field1', 1))
        self.assertTrue(self._record_exists('test_full_sync', 'field1', 2))
        self.assertFalse(self._record_exists('test_full_sync', 'field1', 3))
