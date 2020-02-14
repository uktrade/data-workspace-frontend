from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet


def find_dataset(dataset_uuid, user):
    return get_object_or_404(
        DataSet.objects.live(),
        id=dataset_uuid,
        **{'published': True} if not user.is_superuser else {}
    )
