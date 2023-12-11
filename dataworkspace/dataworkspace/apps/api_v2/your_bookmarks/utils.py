from django.db.models import F, FilteredRelation, Q

from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
)


def filter_bookmarks(datasets, user):
    """
    1. Filter a queryset of datasets or visualisations for only those that have
       been bookmarked by the provided `user`.
    2. Add the date that the bookmark was created to the resulting queryset
    """
    if datasets.model is ReferenceDataset:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "referencedatasetbookmark",
                condition=Q(referencedatasetbookmark__user=user),
            )
        )

    if datasets.model is DataSet:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "datasetbookmark", condition=Q(datasetbookmark__user=user)
            )
        )

    if datasets.model is VisualisationCatalogueItem:
        datasets = datasets.annotate(
            user_bookmark=FilteredRelation(
                "visualisationbookmark", condition=Q(visualisationbookmark__user=user)
            )
        )

    return datasets.exclude(user_bookmark__user=None).annotate(
        created=F("user_bookmark__created_date")
    )
