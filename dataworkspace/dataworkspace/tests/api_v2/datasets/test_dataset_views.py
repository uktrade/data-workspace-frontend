from random import randint

import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.tests import factories


def _dataset_detail(dataset):
    return {
        "id": dataset.id if dataset.type == DataSetType.REFERENCE else str(dataset.id),
        "name": dataset.name,
        "url": dataset.get_absolute_url(),
    }


@pytest.mark.django_db
def test_unauthenticated_list_datasets(unauthenticated_client):
    factories.DatacutDataSetFactory()
    factories.MasterDataSetFactory()
    factories.ReferenceDatasetFactory()
    response = unauthenticated_client.get(reverse("api-v2:datasets:dataset-list"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_authenticated_list_datasets(client, user):
    client.force_login(user)
    factories.DatacutDataSetFactory()
    factories.MasterDataSetFactory()
    factories.ReferenceDatasetFactory()
    response = client.get(reverse("api-v2:datasets:dataset-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 3


@pytest.mark.parametrize(
    "dataset_factory",
    [
        factories.DatacutDataSetFactory,
        factories.MasterDataSetFactory,
        factories.MasterDataSetFactory,
    ],
)
@pytest.mark.django_db
def test_dataset_detail(client, user, dataset_factory):
    client.force_login(user)
    dataset = dataset_factory()
    response = client.get(reverse("api-v2:datasets:dataset-detail", args=(dataset.id,)))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == _dataset_detail(dataset)


@pytest.mark.parametrize(
    "dataset_factory",
    [
        factories.DatacutDataSetFactory,
        factories.MasterDataSetFactory,
        factories.ReferenceDatasetFactory,
        factories.VisualisationCatalogueItemFactory,
    ],
)
@pytest.mark.django_db
def test_dataset_stats(client, user, dataset_factory):
    client.force_login(user)
    dataset = dataset_factory()

    num_page_views = randint(0, 5)
    for _ in range(num_page_views):
        log_event(factories.UserFactory(), EventLog.TYPE_DATASET_VIEW, dataset)

    num_bookmarks = randint(0, 5)
    for _ in range(num_bookmarks):
        dataset.set_bookmark(factories.UserFactory())

    num_collections = randint(0, 5)
    for _ in range(num_collections):
        if dataset.type == DataSetType.VISUALISATION:
            factories.CollectionFactory().visualisation_catalogue_items.add(dataset)
        elif dataset.type == DataSetType.REFERENCE:
            factories.CollectionFactory().datasets.add(
                dataset.reference_dataset_inheriting_from_dataset
            )
        else:
            factories.CollectionFactory().datasets.add(dataset)

    response = client.get(dataset.get_stats_url())
    assert response.status_code == status.HTTP_200_OK
    stats = response.json()
    assert stats["page_views"] == num_page_views
    assert stats["bookmark_count"] == num_bookmarks
    assert stats["collection_count"] == num_collections
