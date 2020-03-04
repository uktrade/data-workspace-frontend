from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.constants import DataSetType


def find_dataset(dataset_uuid, user):
    dataset = get_object_or_404(DataSet.objects.live(), id=dataset_uuid)

    if user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(dataset.type)
    ):
        return dataset

    if not dataset.published:
        raise Http404('No dataset matches the given query.')

    return dataset


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    return {
        DataSetType.REFERENCE.value: 'datasets.manage_unpublished_reference_datasets',
        DataSetType.MASTER.value: 'datasets.manage_unpublished_master_datasets',
        DataSetType.DATACUT.value: 'datasets.manage_unpublished_datacut_datasets',
    }[dataset_type]
