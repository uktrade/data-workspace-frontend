from typing import Union

from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet, ReferenceDataset
from dataworkspace.apps.datasets.constants import DataSetType


def find_dataset(dataset_uuid, user):
    dataset = get_object_or_404(DataSet.objects.live(), id=dataset_uuid)

    if user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(
            get_dataset_type(dataset)
        )
    ):
        return dataset

    if not dataset.published:
        raise Http404('No dataset matches the given query.')

    return dataset


def get_dataset_type(dataset: Union[DataSet, ReferenceDataset]):
    if isinstance(dataset, ReferenceDataset):
        return DataSetType.REFERENCE.value

    return dataset.type


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    if dataset_type == DataSetType.REFERENCE.value:
        return 'datasets.manage_unpublished_reference_datasets'
    elif dataset_type == DataSetType.MASTER.value:
        return 'datasets.manage_unpublished_master_datasets'
    elif dataset_type == DataSetType.DATACUT.value:
        return 'datasets.manage_unpublished_datacut_datasets'

    raise ValueError(f"Unknown dataset type: {dataset_type}")
