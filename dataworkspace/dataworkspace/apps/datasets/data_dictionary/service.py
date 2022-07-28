import logging
from typing import List

from django.shortcuts import get_object_or_404

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.models import (
    SourceTable,
    SourceTableFieldDefinition,
    ReferenceDataset,
    ReferenceDatasetField,
)

from dataworkspace.utils import TYPE_CODES_REVERSED

logger = logging.getLogger(__name__)


class DataDictionary:
    def __init__(self, database_name, schema_name, table_name, object_id):
        self.items = []
        self.database_name = database_name
        self.schema_name = schema_name
        self.table_name = table_name
        self.source_object_id = object_id

    class DataDictionaryUpdateRow:
        def __init__(self, name: str, definition: str):
            self.name = name
            self.definition = definition

    class DataDictionaryRow:
        name: str
        data_type: str
        definition: str

        def __init__(self, name: str, data_type: str, definition: str):
            self.name = name
            self.data_type = data_type
            self.definition = definition

    def append(self, name: str, data_type: str, definition: str):
        item = DataDictionary.DataDictionaryRow(name, data_type, definition)
        self.items.append(item)


class DataDictionaryService:
    @staticmethod
    def _get_source_table(table_uuid):
        logger.info("Looking for a source table with uuid %s", table_uuid)
        matches = SourceTable.objects.filter(pk=table_uuid)

        if not matches.exists():
            logger.debug("Not found")
            return None

        logger.debug("Found")
        return matches.last()

    @staticmethod
    def _get_reference_dataset(uuid):
        logger.debug("Looking for a reference dataset with uuid %s", uuid)
        dataset = get_object_or_404(ReferenceDataset, uuid=uuid)

        return dataset

    @staticmethod
    def _get_dictionary_for_source_table(source_table):
        columns = datasets_db.get_columns(
            source_table.database.memorable_name,
            schema=source_table.schema,
            table=source_table.table,
            include_types=True,
        )
        fields = source_table.field_definitions.all()

        data_dictionary = DataDictionary(
            source_table.database.memorable_name,
            source_table.schema,
            source_table.table,
            source_table.id,
        )
        for name, data_type in columns:
            definition = ""
            if fields.filter(field=name).exists():
                definition = fields.filter(field=name).first().description

            data_dictionary.append(name, data_type, definition)
        return data_dictionary

    @staticmethod
    def _get_dictionary_for_reference_dataset(dataset):
        logger.info("Generating data dictionary for reference dataset %s", dataset.id)
        dictionary = DataDictionary("datasets", "public", dataset.table_name, dataset.uuid)

        for field in dataset.fields.all():
            postgres_type = TYPE_CODES_REVERSED.get(
                ReferenceDatasetField.POSTGRES_TYPE_MAP.get(field.data_type, ""), "Unknown"
            )
            dictionary.append(field.name, postgres_type, field.description)

        return dictionary

    def _update_source_table(
        self, source_table, rows: List[DataDictionary.DataDictionaryUpdateRow]
    ):
        logger.debug("updating source table %s", source_table)

        for row in rows:
            field, created = SourceTableFieldDefinition.objects.get_or_create(
                source_table=source_table, field=row.name, defaults={"description": row.definition}
            )

            if created:
                continue

            if field.description != row.definition:
                logger.debug("Updating %s %s", source_table.name, field.field)
                field.description = row.definition
                field.save()

    def _update_reference_dataset(
        self, dataset, rows: List[DataDictionary.DataDictionaryUpdateRow]
    ):
        logger.debug("updating reference dataset")
        for row in rows:
            field = dataset.fields.filter(column_name=row.name).first()
            if field and field.description != row.definition:
                logger.debug("Updating %s %s", dataset.name, field.name)
                field.description = row.definition
                field.save()

    def get_dictionary(self, entity_uuid) -> DataDictionary:
        source_table = self._get_source_table(entity_uuid)

        if source_table:
            return self._get_dictionary_for_source_table(source_table)

        dataset = self._get_reference_dataset(entity_uuid)
        return self._get_dictionary_for_reference_dataset(dataset)

    def save_dictionary(
        self, entity_uuid, update_rows: List[DataDictionary.DataDictionaryUpdateRow]
    ):

        source_table = self._get_source_table(entity_uuid)
        if source_table:
            return self._update_source_table(source_table, update_rows)

        dataset = self._get_reference_dataset(entity_uuid)
        return self._update_reference_dataset(dataset, update_rows)
