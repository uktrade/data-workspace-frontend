from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet


def find_dataset(dataset_uuid):
    return get_object_or_404(
        DataSet, id=dataset_uuid, published=True
    )
