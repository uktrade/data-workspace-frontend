from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet


def find_dataset(group_slug, set_slug):
    return get_object_or_404(
        DataSet, grouping__slug=group_slug, slug=set_slug, published=True
    )
