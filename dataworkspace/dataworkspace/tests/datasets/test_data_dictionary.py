import pytest
from django.http import Http404
from mock import mock

from dataworkspace.apps.datasets.data_dictionary.service import DataDictionaryService
from dataworkspace.tests import factories


@pytest.mark.django_db()
class TestDataDictionaryService:
    def test_get_dictionary_for_reference_dataset(self):
        mock_user = mock.Mock()
        service = DataDictionaryService(mock_user)

        reference_dataset = factories.ReferenceDatasetFactory.create()
        dictionary = service.get_dictionary(reference_dataset.uuid)
        assert dictionary is not None

    def test_get_dictionary_for_master_dataset(self, metadata_db):
        mock_user = mock.Mock()
        service = DataDictionaryService(mock_user)
        master_dataset = factories.MasterDataSetFactory.create()
        source_table = factories.SourceTableFactory(
            dataset=master_dataset, database=metadata_db, schema="public", table="table1"
        )

        dictionary = service.get_dictionary(source_table.id)
        assert dictionary is not None

    def test_get_dictionary_for_datacut_dataset_fails(self, metadata_db):
        mock_user = mock.Mock()
        service = DataDictionaryService(mock_user)
        datacut = factories.DatacutDataSetFactory.create()

        with pytest.raises(Http404):
            service.get_dictionary(datacut.id)


@pytest.mark.django_db()
class TestReferenceDatasets:
    def test_get_dictionary_lists_all_fields_defined_against_dataset(self, metadata_db):
        reference_dataset = factories.ReferenceDatasetFactory.create(
            external_database=metadata_db, published=True
        )

        assert reference_dataset.external_database is not None

        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            name="id",
            data_type=2,
            is_identifier=True,
            description="Description for id field",
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, name="name", data_type=1
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, name="desc", data_type=1
        )

        reference_dataset.save_record(
            None,
            {
                "reference_dataset": reference_dataset,
                field1.column_name: 1,
                field2.column_name: "Test record",
                field3.column_name: "Test Desc 1",
            },
        )
        reference_dataset.save_record(
            None,
            {
                "reference_dataset": reference_dataset,
                field1.column_name: 2,
                field2.column_name: "Ánd again",
                field3.column_name: None,
            },
        )
        reference_dataset.save()

        service = DataDictionaryService(mock.Mock())
        dictionary = service.get_dictionary(reference_dataset.uuid)

        assert dictionary is not None

        # assert len(dictionary.items) == 3
