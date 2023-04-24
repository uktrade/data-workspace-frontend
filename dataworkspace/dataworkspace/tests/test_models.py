from datetime import date, datetime, timezone
import mock

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import connection, connections, ProgrammingError
from django.db.models import ProtectedError

from freezegun import freeze_time

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
)
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase, BaseTransactionTestCase


class BaseModelsTests(BaseTestCase):
    @staticmethod
    def _table_exists(table_name: str, database=None):
        if database is not None:
            with connections[database].cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", [table_name])
                return cursor.fetchone()[0] == table_name
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s)", [table_name])
            return cursor.fetchone()[0] == table_name

    def _create_and_validate_field(
        self,
        ref_dataset: ReferenceDatasetField,
        field_name: str,
        field_type: str,
        database="default",
    ):
        major_version = ref_dataset.major_version
        schema_version = ref_dataset.schema_version
        rdf = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name=field_name,
            column_name=field_name,
            data_type=field_type,
        )
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name, database=database)
        self.assertIsNotNone(column)
        self.assertEqual(column["column_name"], rdf.column_name)
        self.assertEqual(ref_dataset.major_version, major_version)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)
        return rdf

    @staticmethod
    def _get_column_data(table_name: str, column_name: str, database="default"):
        with connections[database].cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM information_schema.columns
                WHERE table_name=%s
                AND column_name=%s
                """,
                [table_name, column_name],
            )
            columns = [col[0] for col in cursor.description]
            record = cursor.fetchone()
            if record is not None:
                return dict(zip(columns, record))
            return None


class ReferenceDatasetsMixin:
    databases = ["default", "test_external_db", "test_external_db2"]

    def _add_record_to_dataset(self, ref_dataset):
        minor_version = ref_dataset.minor_version
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        record = ref_dataset.get_record_by_custom_id(1)
        self.assertIsNotNone(record)
        record = ref_dataset.get_record_by_internal_id(record.id)
        self.assertIsNotNone(record)
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, minor_version + 1)


class TestTransactionReferenceDatasets(ReferenceDatasetsMixin, BaseTransactionTestCase):
    def test_republish_without_edit_does_not_increment_version(self):
        ref_dataset = self._create_reference_dataset(
            table_name="test_add_record_repub", published=True
        )
        self._add_record_to_dataset(ref_dataset)
        self.assertEqual(ref_dataset.version, "1.1")
        self.assertEqual(ref_dataset.published_version, "1.1")

        ref_dataset = ReferenceDataset.objects.get(pk=ref_dataset.pk)
        ref_dataset.published = False
        ref_dataset.save()
        self.assertEqual(ref_dataset.version, "1.1")
        self.assertEqual(ref_dataset.published_version, "1.1")

        field6 = ReferenceDatasetField.objects.create(
            reference_dataset_id=ref_dataset.pk,
            name="field6",
            column_name="field6",
            required=False,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
        )
        ref_dataset.save_record(field6.pk, {"reference_dataset": ref_dataset, field6.name: 1})
        ref_dataset.save_record(field6.pk, {"reference_dataset": ref_dataset, field6.name: 2})

        self.assertEqual(ref_dataset.version, "1.3")
        self.assertEqual(ref_dataset.published_version, "1.1")

        ref_dataset = ReferenceDataset.objects.get(pk=ref_dataset.pk)
        ref_dataset.published = True
        ref_dataset.save()
        self.assertEqual(ref_dataset.version, "1.2")
        self.assertEqual(ref_dataset.published_version, "1.2")


class TestDatasets(BaseModelsTests):
    @freeze_time("2019-02-01 02:00:00", as_kwarg="frozen_datetime")
    def test_create_master_dataset(self, frozen_datetime):
        dataset = DataSet.objects.create(
            type=DataSetType.MASTER,
            name="Test Dataset",
            slug="test-dataset",
            short_description="Short description",
            description="Long description",
            published=True,
        )
        self.assertEqual(dataset.published_at, datetime(2019, 2, 1, 2, 0, 0, tzinfo=timezone.utc))

        # Changing the dataset should and saving should not update the published_at date
        frozen_datetime.tick()
        dataset.description = "Modified long description"
        dataset.save()

        self.assertEqual(dataset.description, "Modified long description")
        self.assertEqual(dataset.published_at, datetime(2019, 2, 1, 2, 0, 0, tzinfo=timezone.utc))


class TestReferenceDatasets(ReferenceDatasetsMixin, BaseModelsTests):
    @freeze_time("2019-02-01 02:00:00")
    def test_create_reference_dataset(self):
        ref_dataset = self._create_reference_dataset()
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 0)
        self.assertEqual(ref_dataset.schema_version, 0)
        self.assertEqual(ref_dataset.published_major_version, 1)
        self.assertEqual(ref_dataset.published_minor_version, 0)
        self.assertEqual(
            ref_dataset.initial_published_at,
            datetime(2019, 2, 1, 2, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(ref_dataset.published_at, datetime(2019, 2, 1, 2, 0, tzinfo=timezone.utc))

    def test_create_unpublished_reference_dataset(self):
        ref_dataset = self._create_reference_dataset(published=False)
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 0)
        self.assertEqual(ref_dataset.schema_version, 0)
        self.assertEqual(ref_dataset.published_major_version, 0)
        self.assertEqual(ref_dataset.published_minor_version, 0)
        self.assertIsNone(ref_dataset.initial_published_at)
        self.assertIsNone(ref_dataset.published_at)

    def test_edit_reference_dataset_table_name(self):
        ref_dataset = self._create_reference_dataset()
        ref_dataset.table_name = "ref_new_table_name"
        ref_dataset.save()

        # Ensure the table was created in the db
        self.assertFalse(self._table_exists("ref_test_dataset"))
        self.assertTrue(self._table_exists(ref_dataset.table_name))
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 0)
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
        ref_dataset = self._create_reference_dataset(table_name="testing")

        # Character field
        self._create_and_validate_field(
            ref_dataset, "char_field", ReferenceDatasetField.DATA_TYPE_CHAR
        )

        # Integer field
        self._create_and_validate_field(
            ref_dataset, "int_field", ReferenceDatasetField.DATA_TYPE_INT
        )

        # Float field
        self._create_and_validate_field(
            ref_dataset, "float_field", ReferenceDatasetField.DATA_TYPE_FLOAT
        )

        # Date field
        self._create_and_validate_field(
            ref_dataset, "date_field", ReferenceDatasetField.DATA_TYPE_DATE
        )

        # Time field
        self._create_and_validate_field(
            ref_dataset, "time_field", ReferenceDatasetField.DATA_TYPE_TIME
        )

        # Datetime field
        self._create_and_validate_field(
            ref_dataset, "datetime_field", ReferenceDatasetField.DATA_TYPE_DATETIME
        )

        # Boolean field
        self._create_and_validate_field(
            ref_dataset, "boolean_field", ReferenceDatasetField.DATA_TYPE_BOOLEAN
        )

    def test_edit_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset(
            table_name="test_edit_reference_dataset_field"
        )

        # Change column name - should not affect the db column
        rdf = self._create_and_validate_field(
            ref_dataset, "char_field", ReferenceDatasetField.DATA_TYPE_CHAR
        )
        rdf.name = "updated_field"
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertIsNotNone(column)
        self.assertEqual(column["column_name"], rdf.column_name)

        # Change data type

        # Char -> Int
        rdf = self._create_and_validate_field(
            ref_dataset, "test_field", ReferenceDatasetField.DATA_TYPE_CHAR
        )
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_INT
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "int4")

        # Int -> Float
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "float8")

        # Float -> Date
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "date")

        # Date -> Time
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "time")

        # Time -> Datetime
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "timestamp")

        # Datetime -> Bool
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_BOOLEAN
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["udt_name"], "bool")

        # Ensure name change is reflected in the db
        rdf.column_name = "updated"
        rdf.save()
        column = self._get_column_data(ref_dataset.table_name, rdf.column_name)
        self.assertEqual(column["column_name"], rdf.column_name)

    def test_delete_reference_dataset_field(self):
        ref_dataset = self._create_reference_dataset(
            table_name="test_delete_reference_dataset_field"
        )
        field = self._create_and_validate_field(
            ref_dataset, "test_field", ReferenceDatasetField.DATA_TYPE_CHAR
        )
        self.assertEqual(ref_dataset.major_version, 1)
        schema_version = ref_dataset.schema_version
        field.delete()
        column = self._get_column_data(ref_dataset.table_name, "test_field")
        self.assertIsNone(column)
        self.assertEqual(ref_dataset.major_version, 2)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)

    def test_add_record_to_published_dataset(self):
        ref_dataset = self._create_reference_dataset(table_name="test_add_record", published=True)
        self._add_record_to_dataset(ref_dataset)
        self.assertEqual(ref_dataset.version, "1.1")
        self.assertEqual(ref_dataset.published_version, "1.1")

    def test_add_record_to_unpublished_dataset_then_publish(self):
        ref_dataset = self._create_reference_dataset(table_name="test_add_record", published=False)
        self._add_record_to_dataset(ref_dataset)
        self.assertEqual(ref_dataset.version, "1.1")
        self.assertEqual(ref_dataset.published_version, "0.0")

        ref_dataset.published = True
        ref_dataset.save()
        self.assertEqual(ref_dataset.version, "1.0")
        self.assertEqual(ref_dataset.published_version, "1.0")

    def test_edit_record(self):
        ref_dataset = self._create_reference_dataset(table_name="test_edit_record")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        self.assertEqual(ref_dataset.major_version, 1)
        with freeze_time("2020-01-01 00:00:00") as frozen_time:
            ref_dataset.save_record(
                None,
                {
                    "reference_dataset": ref_dataset,
                    field1.column_name: 1,
                    field2.column_name: "testing...",
                },
            )
            self.assertEqual(ref_dataset.major_version, 1)
            self.assertEqual(ref_dataset.minor_version, 1)
            record = ref_dataset.get_record_by_custom_id(1)
            self.assertEqual(record.updated_date, datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc))
            updated_date = datetime(2020, 1, 1, 0, 10, tzinfo=timezone.utc)
            frozen_time.move_to(updated_date)
            ref_dataset.save_record(
                record.id,
                {
                    "reference_dataset": ref_dataset,
                    field1.column_name: 999,
                    field2.column_name: "changed",
                },
            )
            record = ref_dataset.get_record_by_custom_id(999)
            self.assertEqual(record.updated_date, updated_date)
            self.assertRaises(ObjectDoesNotExist, ref_dataset.get_record_by_custom_id, 1)
            self.assertEqual(ref_dataset.major_version, 1)
            self.assertEqual(ref_dataset.minor_version, 2)
            self.assertIsNotNone(ref_dataset.get_record_by_custom_id(999))

    def test_delete_record(self):
        ref_dataset = self._create_reference_dataset(table_name="test_delete_record")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 0)
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 1)
        record = ref_dataset.get_record_by_custom_id(1)
        ref_dataset.delete_record(record.id)
        self.assertRaises(ObjectDoesNotExist, ref_dataset.get_record_by_custom_id, 1)
        self.assertEqual(ref_dataset.major_version, 1)
        self.assertEqual(ref_dataset.minor_version, 2)

    def test_delete_linked_to_reference_dataset(self):
        # Test that ref dataset deletion fails if other datasets link to it

        # Create a linked_to dataset and id field
        linked_to_dataset = factories.ReferenceDatasetFactory.create(table_name="linked_to")
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_to_dataset,
            is_identifier=True,
        )

        # Create a linked from dataset and id, link fields
        linked_from_dataset = factories.ReferenceDatasetFactory.create(table_name="linked_from")
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_from_dataset,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_from_dataset,
            is_identifier=True,
            relationship_name="rel",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
        )

        # Deleting the dataset should fail
        self.assertRaises(ProtectedError, lambda _: linked_to_dataset.delete(), 1)

    def test_linked_dataset_field_foreign_key(self):
        # Ensure a reference dataset field cannot link to a linked reference dataset field
        ref_dataset1 = self._create_reference_dataset(table_name="dataset_1")
        ref_dataset2 = self._create_reference_dataset(table_name="dataset_2")
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset2,
            name="identifier",
            column_name="identifier",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset1,
            name="identifier",
            column_name="identifier",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset1,
            name="link",
            relationship_name="link",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=ref_dataset2.fields.get(is_identifier=True),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Unable to link reference dataset fields to another field that is itself linked",
        ):
            ReferenceDatasetField.objects.create(
                reference_dataset=ref_dataset2,
                name="link",
                column_name="link",
                data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                linked_reference_dataset_field=ref_dataset1.fields.get(name="link"),
            )

    def test_circular_linked_dataset_field(self):
        # Ensure a reference dataset field cannot link to a reference dataset field
        # in a dataset that has a field pointing back to itself
        ref_dataset1 = self._create_reference_dataset(table_name="dataset_1")
        ref_dataset2 = self._create_reference_dataset(table_name="dataset_2")
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset2,
            name="identifier",
            column_name="identifier",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset1,
            name="identifier",
            column_name="identifier",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset1,
            name="link",
            relationship_name="link",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=ref_dataset2.fields.get(is_identifier=True),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Unable to link reference dataset fields to another field that points back to this dataset (circular link)",
        ):
            ReferenceDatasetField.objects.create(
                reference_dataset=ref_dataset2,
                name="link",
                column_name="link",
                data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                linked_reference_dataset_field=ref_dataset1.fields.get(name="identifier"),
            )

    def test_reference_dataset_ordering(self):
        # Create a reference dataset
        # Create some fields (including a linked field)
        # Add some records
        # Test sorting on different fields and directions

        # Add a reference dataset and a dataset it can link to
        ref_dataset = self._create_reference_dataset(table_name="ordering_test_1")
        linked_to_dataset = self._create_reference_dataset(table_name="ordering_test_2")

        # Add id and name fields to the linked to dataset
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="refid",
            column_name="refid",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="name",
            column_name="name",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )

        # Add id, name and link fields to the main reference dataset
        id_field = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="refid",
            column_name="refid",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        name_field = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="name",
            column_name="name",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        link_field = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="link",
            relationship_name="link",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
        )

        # Create some records in the linked_to dataset
        linked_to_record1 = linked_to_dataset.save_record(
            None,
            {"reference_dataset": linked_to_dataset, "refid": 1, "name": "Axolotl"},
        )
        linked_to_record2 = linked_to_dataset.save_record(
            None,
            {"reference_dataset": linked_to_dataset, "refid": 2, "name": "Aarvark"},
        )

        # Create some records in the main dataset
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                "refid": 1,
                "name": "Zanzibar",
                "link_id": linked_to_record1.id,
            },
        )
        ref_dataset.save_record(
            None, {"reference_dataset": ref_dataset, "refid": 2, "name": "Xebec"}
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                "refid": 3,
                "name": "Vugg",
                "link_id": linked_to_record2.id,
            },
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                "refid": 4,
                "name": "Logjam",
                "link_id": linked_to_record1.id,
            },
        )
        ref_dataset.save()

        # Default sort order should be updated date
        updated_dates = [x.updated_date for x in ref_dataset.get_records()]
        self.assertEqual(updated_dates, list(sorted(updated_dates)))

        # Test setting the sort direction to desc
        ref_dataset.sort_direction = ref_dataset.SORT_DIR_DESC
        ref_dataset.save()
        updated_dates = [x.updated_date for x in ref_dataset.get_records()]
        self.assertEqual(updated_dates, list(reversed(sorted(updated_dates))))

        # Test ordering by name
        ref_dataset.sort_field = name_field
        ref_dataset.sort_direction = ref_dataset.SORT_DIR_ASC
        ref_dataset.save()
        names = [x.name for x in ref_dataset.get_records()]
        self.assertEqual(names, sorted(names))

        # Test name reversed
        ref_dataset.sort_direction = ref_dataset.SORT_DIR_DESC
        ref_dataset.save()
        names = [x.name for x in ref_dataset.get_records()]
        self.assertEqual(names, list(reversed(sorted(names))))

        # Test sort by id
        ref_dataset.sort_field = id_field
        ref_dataset.sort_direction = ref_dataset.SORT_DIR_ASC
        ref_dataset.save()
        ids = [x.refid for x in ref_dataset.get_records()]
        self.assertEqual(ids, sorted(ids))

        # Test sort by linked field display name
        ref_dataset.sort_field = link_field
        ref_dataset.save()

        linked_names = [
            getattr(x.link, link_field.linked_reference_dataset_field.column_name)
            for x in ref_dataset.get_records()
            if x.link is not None
        ]
        self.assertEqual(linked_names, sorted(linked_names))

        # Test sorting by linked display name descending
        ref_dataset.sort_direction = ref_dataset.SORT_DIR_DESC
        ref_dataset.save()
        linked_names = [
            getattr(x.link, link_field.linked_reference_dataset_field.column_name)
            for x in ref_dataset.get_records()
            if x.link is not None
        ]
        self.assertEqual(linked_names, list(reversed(sorted(linked_names))))

    def test_data_grid_column_config(self):
        ds = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            sort_order=1,
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds, data_type=ReferenceDatasetField.DATA_TYPE_INT, sort_order=2
        )
        field3 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds, data_type=ReferenceDatasetField.DATA_TYPE_DATE, sort_order=3
        )
        linked_to_dataset = self._create_reference_dataset(table_name="linked_to_external_dataset")
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field4 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            relationship_name="link",
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
            sort_order=4,
        )
        assert ds.get_column_config() == [
            {
                "headerName": field1.name,
                "field": field1.column_name,
                "sortable": True,
                "filter": "agTextColumnFilter",
            },
            {
                "headerName": field2.name,
                "field": field2.column_name,
                "sortable": True,
                "filter": "agNumberColumnFilter",
            },
            {
                "headerName": field3.name,
                "field": field3.column_name,
                "sortable": True,
                "filter": "agDateColumnFilter",
            },
            {
                "headerName": field4.name,
                "field": f"{field4.relationship_name}_{field4.linked_reference_dataset_field.column_name}",
                "sortable": True,
                "filter": "agNumberColumnFilter",
            },
        ]

    def test_data_grid_data(self):
        linked_to_dataset = self._create_reference_dataset(table_name="linked_to_external_dataset")
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_display_name=True,
        )
        linked_to_record = linked_to_dataset.save_record(
            None,
            {"reference_dataset": linked_to_dataset, "field1": 1, "field2": "a record"},
        )

        ds = factories.ReferenceDatasetFactory.create()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds, data_type=ReferenceDatasetField.DATA_TYPE_CHAR
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds, data_type=ReferenceDatasetField.DATA_TYPE_INT
        )
        field3 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds, data_type=ReferenceDatasetField.DATA_TYPE_DATE
        )
        field4 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            relationship_name="link1",
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
        )
        field5 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=ds,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            relationship_name="link2",
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_display_name=True),
        )
        record1 = ds.save_record(
            None,
            {
                "reference_dataset": ds,
                field1.column_name: "Some text",
                field2.column_name: 123,
                field3.column_name: date(2020, 1, 1),
                "link1_id": None,
                "link2_id": None,
            },
        )
        record2 = ds.save_record(
            None,
            {
                "reference_dataset": ds,
                field1.column_name: "More text",
                field2.column_name: 321,
                field3.column_name: date(2019, 12, 31),
                "link1_id": linked_to_record.id,
                "link2_id": linked_to_record.id,
            },
        )
        assert ds.get_grid_data() == [
            {
                "_id": record1.id,
                field1.column_name: "Some text",
                field2.column_name: 123,
                field3.column_name: date(2020, 1, 1),
                f"link1_{field4.linked_reference_dataset_field.column_name}": None,
                f"link2_{field5.linked_reference_dataset_field.column_name}": None,
            },
            {
                "_id": record2.id,
                field1.column_name: "More text",
                field2.column_name: 321,
                field3.column_name: date(2019, 12, 31),
                f"link1_{field4.linked_reference_dataset_field.column_name}": 1,
                f"link2_{field5.linked_reference_dataset_field.column_name}": "a record",
            },
        ]


class TestSourceLinkModel(BaseTestCase):
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    def test_delete_local_source_link(self, mock_client):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
        )
        link = factories.SourceLinkFactory(
            id="158776ec-5c40-4c58-ba7c-a3425905ec45",
            dataset=dataset,
            link_type=SourceLink.TYPE_LOCAL,
            url="s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.txt",
        )
        link.delete()
        self.assertFalse(
            SourceLink.objects.filter(id="158776ec-5c40-4c58-ba7c-a3425905ec45").exists()
        )
        mock_client().head_object.assert_called_once()
        mock_client().delete_object.assert_called_once_with(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key=link.url
        )

    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    def test_delete_external_source_link(self, mock_client):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
        )
        link = factories.SourceLinkFactory(
            id="158776ec-5c40-4c58-ba7c-a3425905ec45",
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url="http://example.com",
        )
        link.delete()
        self.assertFalse(
            SourceLink.objects.filter(id="158776ec-5c40-4c58-ba7c-a3425905ec45").exists()
        )
        mock_client.assert_not_called()


class TestExternalModels(BaseModelsTests):
    databases = ["default", "test_external_db", "test_external_db2"]

    def _create_reference_dataset(self, **kwargs):
        return super()._create_reference_dataset(
            external_database=factories.DatabaseFactory.create(), **kwargs
        )

    @staticmethod
    def _record_exists(table_name, identifier_field, record_id, database="test_external_db"):
        with connections[database].cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM {} WHERE {}=%s".format(table_name, identifier_field),
                [record_id],
            )
            return cursor.fetchone()[0] == 1

    def test_create_reference_dataset_external(self):
        ref_dataset = self._create_reference_dataset()
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db"))

    def test_edit_reference_dataset_table_name_external(self):
        ref_dataset = self._create_reference_dataset(table_name="test_edit_table")
        self.assertTrue(self._table_exists("test_edit_table", database="test_external_db"))
        ref_dataset.table_name = "new_table_name"
        ref_dataset.save()
        self.assertFalse(self._table_exists("test_edit_table", database="test_external_db"))
        self.assertTrue(self._table_exists("new_table_name", database="test_external_db"))

    def test_delete_reference_dataset_external(self):
        # Ensure external tables are removed when the reference dataset deleted
        ref_dataset = self._create_reference_dataset(table_name="test_del_external")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db"))
        ref_dataset.delete()
        self.assertFalse(self._table_exists(ref_dataset.table_name, database="test_external_db"))

    def test_create_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(table_name="thisisatest")

        # Character field
        self._create_and_validate_field(
            ref_dataset,
            "char_field",
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database="test_external_db",
        )

        # Integer field
        self._create_and_validate_field(
            ref_dataset,
            "int_field",
            ReferenceDatasetField.DATA_TYPE_INT,
            database="test_external_db",
        )

        # Float field
        self._create_and_validate_field(
            ref_dataset,
            "float_field",
            ReferenceDatasetField.DATA_TYPE_FLOAT,
            database="test_external_db",
        )

        # Date field
        self._create_and_validate_field(
            ref_dataset,
            "date_field",
            ReferenceDatasetField.DATA_TYPE_DATE,
            database="test_external_db",
        )

        # Time field
        self._create_and_validate_field(
            ref_dataset,
            "time_field",
            ReferenceDatasetField.DATA_TYPE_TIME,
            database="test_external_db",
        )

        # Datetime field
        self._create_and_validate_field(
            ref_dataset,
            "datetime_field",
            ReferenceDatasetField.DATA_TYPE_DATETIME,
            database="test_external_db",
        )

        # Boolean field
        self._create_and_validate_field(
            ref_dataset,
            "boolean_field",
            ReferenceDatasetField.DATA_TYPE_BOOLEAN,
            database="test_external_db",
        )

        # UUID field
        self._create_and_validate_field(
            ref_dataset,
            "uuid_field",
            ReferenceDatasetField.DATA_TYPE_UUID,
            database="test_external_db",
        )

    def test_edit_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(
            table_name="test_edit_reference_dataset_field"
        )

        # Change column name - should not affect the db column
        rdf = self._create_and_validate_field(
            ref_dataset,
            "char_field",
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database="test_external_db",
        )
        rdf.name = "updated_field"
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertIsNotNone(column)
        self.assertEqual(column["column_name"], rdf.column_name)

        # Change data type

        # Char -> Int
        rdf = self._create_and_validate_field(
            ref_dataset,
            "test_field",
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database="test_external_db",
        )
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_INT
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "int4")

        # Int -> Float
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "float8")

        # Float -> Date
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "date")

        # Date -> Time
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "time")

        # Time -> Datetime
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "timestamp")

        # Datetime -> Bool
        rdf.data_type = ReferenceDatasetField.DATA_TYPE_BOOLEAN
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["udt_name"], "bool")

        # Ensure name change is reflected in the db
        rdf.column_name = "updated"
        rdf.save()
        column = self._get_column_data(
            ref_dataset.table_name, rdf.column_name, database="test_external_db"
        )
        self.assertEqual(column["column_name"], rdf.column_name)

    def test_delete_reference_dataset_field_external(self):
        ref_dataset = self._create_reference_dataset(table_name="test_delete_field")
        field = self._create_and_validate_field(
            ref_dataset,
            "test_field",
            ReferenceDatasetField.DATA_TYPE_CHAR,
            database="test_external_db",
        )
        schema_version = ref_dataset.schema_version
        field.delete()
        column = self._get_column_data(
            ref_dataset.table_name, "test_field", database="test_external_db"
        )
        self.assertIsNone(column)
        self.assertEqual(ref_dataset.major_version, 2)
        self.assertEqual(ref_dataset.schema_version, schema_version + 1)

    def test_add_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name="test_add_record")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field3",
            column_name="field3",
            data_type=ReferenceDatasetField.DATA_TYPE_UUID,
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        self.assertTrue(self._record_exists("test_add_record", "field1", 1))

    def test_edit_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name="test_edit_record")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field3",
            column_name="field3",
            data_type=ReferenceDatasetField.DATA_TYPE_UUID,
        )
        self.assertEqual(ref_dataset.major_version, 1)
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        self.assertTrue(self._record_exists("test_edit_record", "field1", 1))

    def test_delete_record_external(self):
        ref_dataset = self._create_reference_dataset(table_name="test_delete_record")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field3",
            column_name="field3",
            data_type=ReferenceDatasetField.DATA_TYPE_UUID,
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "testing...",
            },
        )
        record = ref_dataset.get_record_by_custom_id(1)
        ref_dataset.delete_record(record.id)
        self.assertFalse(self._record_exists("test_delete_record", "field1", 1))

    def test_create_external_database(self):
        # Ensure existing records are synced to any new database on creation
        ref_dataset = ReferenceDataset.objects.create(
            name="Test Reference Dataset 1",
            table_name="ext_db_test",
            short_description="Testing...",
            slug="test-reference-dataset-1",
            published=True,
            external_database=factories.DatabaseFactory.create(),
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 1})
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 2})
        self.assertTrue(self._record_exists("ext_db_test", "field1", 1))
        self.assertTrue(self._record_exists("ext_db_test", "field1", 2))

    def test_edit_add_external_database(self):
        ref_dataset = ReferenceDataset.objects.create(
            name="Test Reference Dataset 1",
            table_name="ext_db_edit_test",
            short_description="Testing...",
            slug="test-reference-dataset-1",
            published=True,
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 1})
        ref_dataset.external_database = Database.objects.get_or_create(
            memorable_name="test_external_db2"
        )[0]
        ref_dataset.save()

        self.assertFalse(self._table_exists(ref_dataset.table_name, database="test_external_db"))
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db2"))
        self.assertTrue(
            self._record_exists("ext_db_edit_test", "field1", 1, database="test_external_db2")
        )

    def test_edit_change_external_database(self):
        ref_dataset = ReferenceDataset.objects.create(
            name="Test Reference Dataset 1",
            table_name="ext_db_change_test",
            short_description="Testing...",
            slug="test-reference-dataset-1",
            published=True,
            external_database=factories.DatabaseFactory.create(),
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 1})
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 2})
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db"))
        ref_dataset.external_database = factories.DatabaseFactory.create(
            memorable_name="test_external_db2"
        )
        ref_dataset.save()
        self.assertFalse(self._table_exists(ref_dataset.table_name, database="test_external_db"))
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db2"))
        self.assertTrue(
            self._record_exists("ext_db_change_test", "field1", 1, database="test_external_db2")
        )
        self.assertTrue(
            self._record_exists("ext_db_change_test", "field1", 2, database="test_external_db2")
        )

    def test_edit_remove_external_database(self):
        ref_dataset = ReferenceDataset.objects.create(
            name="Test Reference Dataset 1",
            table_name="ext_db_delete_test",
            short_description="Testing...",
            slug="test-reference-dataset-1",
            published=True,
            external_database=factories.DatabaseFactory.create(),
        )
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 1})
        ref_dataset.save_record(None, {"reference_dataset": ref_dataset, field1.column_name: 2})
        self.assertTrue(self._table_exists(ref_dataset.table_name, database="test_external_db"))
        ref_dataset.external_database = None
        ref_dataset.save()
        self.assertFalse(self._table_exists(ref_dataset.table_name, database="test_external_db"))

    def test_external_database_full_sync(self):
        ref_dataset = self._create_reference_dataset(table_name="test_full_sync")
        field1 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=ref_dataset,
            name="field3",
            column_name="field3",
            data_type=ReferenceDatasetField.DATA_TYPE_UUID,
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 1,
                field2.column_name: "record 1",
            },
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 2,
                field2.column_name: "record 2",
            },
        )
        ref_dataset.save_record(
            None,
            {
                "reference_dataset": ref_dataset,
                field1.column_name: 3,
                field2.column_name: "record 3",
            },
        )
        # Sync with ext db
        ref_dataset.sync_to_external_database("test_external_db")
        # Check that the records exist in ext db
        self.assertTrue(self._record_exists("test_full_sync", "field1", 1))
        self.assertTrue(self._record_exists("test_full_sync", "field1", 2))
        self.assertTrue(self._record_exists("test_full_sync", "field1", 3))
        # Delete a record
        ref_dataset.get_records().last().delete()
        # Sync with ext db
        ref_dataset.sync_to_external_database("test_external_db")
        # Ensure record was deleted externally
        self.assertTrue(self._record_exists("test_full_sync", "field1", 1))
        self.assertTrue(self._record_exists("test_full_sync", "field1", 2))
        self.assertFalse(self._record_exists("test_full_sync", "field1", 3))

    @mock.patch("dataworkspace.apps.datasets.models.connections")
    def test_create_reference_dataset_external_error(self, mock_conn):
        # Test that an error thrown while creating an external table
        # rolls back local table change
        mock_conn.__getitem__.return_value.schema_editor.side_effect = Exception("Fail")
        try:
            self._create_reference_dataset(table_name="test_create_external_error")
        except Exception:  # pylint: disable=broad-except
            pass
        self.assertFalse(self._table_exists("test_create_external_error"))
        self.assertFalse(
            self._table_exists("test_create_external_error", database="test_external_db")
        )

    def test_edit_reference_dataset_external_error(self):
        # Test that when an exception occurs during external database save
        # the local database is rolled back
        ref_dataset = self._create_reference_dataset(table_name="edit_table_ext_error")
        ref_dataset.table_name = "updated_edit_table_ext_error"
        with mock.patch("dataworkspace.apps.datasets.models.connections") as mock_conn:
            mock_ext_conn = mock.Mock()
            mock_ext_conn.schema_editor.side_effect = ProgrammingError("fail!")

            # Ensure the local db is updated and the external db throws an error
            def mock_getitem(_, alias):
                if alias == "default":
                    return connection
                return mock_ext_conn

            mock_conn.__getitem__ = mock_getitem
            try:
                ref_dataset.save()
            except ProgrammingError:
                pass

        # We should still have two tables with the original table name and no
        # tables with the updated table name
        self.assertTrue(self._table_exists("edit_table_ext_error"))
        self.assertTrue(self._table_exists("edit_table_ext_error", database="test_external_db"))
        self.assertFalse(self._table_exists("updated_edit_table_ext_error"))
        self.assertFalse(
            self._table_exists("updated_edit_table_ext_error", database="test_external_db")
        )

    def test_create_linked_reference_datasets(self):
        # Ensure sync works when two tables are linked and only the linked
        # from table is external

        # Create a non-external ref dataset
        linked_to_dataset = self._create_reference_dataset(table_name="linked_to_external_dataset")

        # Create an identifier field for the internal dataset
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )

        # Create an external linked_from dataset and id, link fields
        linked_from_dataset = self._create_reference_dataset(
            table_name="linked_from_external_dataset"
        )

        # Create identifier and link fields for the external dataset
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_from_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_from_dataset,
            name="field2",
            relationship_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
        )

        self.assertTrue(self._table_exists("linked_to_external_dataset"))
        self.assertTrue(
            self._table_exists("linked_to_external_dataset", database="test_external_db")
        )
        self.assertTrue(self._table_exists("linked_from_external_dataset"))
        self.assertTrue(
            self._table_exists("linked_from_external_dataset", database="test_external_db")
        )

    def test_delete_reference_dataset_sort_field(self):
        # Create a dataset to link to
        linked_to_dataset = self._create_reference_dataset(table_name="linked_to_external_dataset")
        # Create an identifier field
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        # Create a display name field
        name_field = ReferenceDatasetField.objects.create(
            reference_dataset=linked_to_dataset,
            name="field2",
            column_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=False,
        )
        # Set the sort field
        linked_to_dataset.sort_field = name_field
        linked_to_dataset.save()

        # Create a linked_from dataset
        linked_from_dataset = self._create_reference_dataset(
            table_name="linked_from_external_dataset"
        )
        # Create identifier field
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_from_dataset,
            name="field1",
            column_name="field1",
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            reference_dataset=linked_from_dataset,
            name="field2",
            relationship_name="field2",
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=linked_to_dataset.fields.get(is_identifier=True),
        )

        # Deleting the name field should work even though it's the sort field
        name_field.delete()
        linked_to_dataset.refresh_from_db()
        self.assertIsNone(linked_to_dataset.sort_field)
