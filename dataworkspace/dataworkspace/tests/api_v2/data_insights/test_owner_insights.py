import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.apps.datasets.models import DataSetType
from dataworkspace.tests import factories

ENDPOINT = "api-v1:data_insights:owner_insights"


@pytest.mark.django_db
def test_unauthenticated_insights_data(unauthenticated_client):
    response = unauthenticated_client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_basic_response(client, user):
    client.force_login(user)
    ds = factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=True,
        type=DataSetType.MASTER,
        id=1,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is another dataset",
        published=True,
        type=DataSetType.REFERENCE,
        id=2,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="and another",
        published=True,
        type=DataSetType.VISUALISATION,
        id=3,
    )
    factories.SourceTableFactory(
        name="my-source",
        table="my_table",
        dataset=ds,
    )
    factories.AccessRequestFactory(requester=user, catalogue_item_id=ds.id)
    response = client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    user_results = [r for r in results if r["email"] == user.email]
    assert len(user_results) == 1
    owned_datasets = user_results[0]["owned_datasets"]
    assert len(owned_datasets) == 3
    assert [d for d in owned_datasets if d["name"] == ds.name][0]["access_request_count"] == 1
    assert len(user_results[0]["owned_source_tables"]) == 1


@pytest.mark.django_db
def test_unpublished_data_doesnt_appear_in_response(client, user):
    client.force_login(user)
    ds = factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=False,
        type=DataSetType.MASTER,
        id=1,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is another dataset",
        published=False,
        type=DataSetType.REFERENCE,
        id=2,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="and another",
        published=False,
        type=DataSetType.VISUALISATION,
        id=3,
    )
    factories.SourceTableFactory(
        name="my-source",
        table="my_table",
        dataset=ds,
    )
    response = client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    user_results = [r for r in results if r["email"] == user.email]
    assert len(user_results) == 1
    assert len(user_results[0]["owned_datasets"]) == 0
    assert len(user_results[0]["owned_source_tables"]) == 0
