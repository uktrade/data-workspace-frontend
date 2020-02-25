import pytest

from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    get_dataset_type,
)
from dataworkspace.tests import factories


@pytest.mark.django_db
def test_get_dataset_type():
    reference = factories.ReferenceDatasetFactory.create()
    datacut = factories.DataSetFactory(type=DataSet.TYPE_DATA_CUT)
    master = factories.DataSetFactory(type=DataSet.TYPE_MASTER_DATASET)

    assert get_dataset_type(reference) == 0
    assert get_dataset_type(master) == 1
    assert get_dataset_type(datacut) == 2


def test_dataset_type_to_manage_unpublished_permission_codename():
    assert (
        dataset_type_to_manage_unpublished_permission_codename(0)
        == 'datasets.manage_unpublished_reference_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSet.TYPE_DATA_CUT)
        == 'datasets.manage_unpublished_datacut_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(
            DataSet.TYPE_MASTER_DATASET
        )
        == 'datasets.manage_unpublished_master_datasets'
    )
