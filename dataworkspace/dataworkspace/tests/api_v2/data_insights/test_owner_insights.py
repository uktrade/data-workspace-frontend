import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories

ENDPOINT = "api-v2:data_insights:owner_insights"


@pytest.mark.django_db
def test_unauthenticated_insights_data(unauthenticated_client):
    response = unauthenticated_client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_one_published_dataset_returns_count(client, user):
    client.force_login(user)
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=True,
    )
    response = client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_200_OK
    print(response.json())
    assert 5 > 9
    managed_data = response.json()["results"][0]
    assert managed_data["count"] == 1
    managed_data_url = f"{reverse('datasets:find_datasets')}?q=&sort=relevance&my_datasets=owned"
    assert managed_data["managed_data_url"] == managed_data_url


"""
class OwnerInsightsAPITest(APITestCase):
    def setUp(self):
        self.user = factories.UserFactory(email="terry.test@businessandtrade.gov.uk")
        factories.DataSetFactory(
            information_asset_owner=self.user,
            name="this is one dataset",
            published=True,
        )

    @pytest.mark.django_db
    def test_get_owner_insights(self):
        self.setUp()
        response = self.client.get(reverse(ENDPOINT)).json()
        results = [u for u in response["results"] if u["email"] == 'terry.test@businessandtrade.gov.uk']
        print(results)
        assert len(results) == 1
"""
"""
@pytest.mark.django_db
def test_basic_response(client, user):
    client.force_login(user)
    user2 = factories.UserFactory()
    ds = factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=True,
    )
    factories.SourceTableFactory(dataset=ds, schema="public")
    factories.SourceTableFactory(dataset=ds, schema="public")
    factories.AccessRequestFactory(catalogue_item_id=ds.id, requester=user2)
    factories.EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_CHANGED_DATASET_DESCRIPTION,
        related_object=ds,
    )
    response = client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_200_OK
    response_json = response.json()
    results = response_json["results"]
    print(results)
    assert response_json["count"] == 1 and len(results) == 1
    assert results[0]["email"] == "frank.exampleson@test.com"
    owned_datasets = results[0]["owned_datasets"]
    assert len(owned_datasets) == 1
    assert owned_datasets[0]["name"] == "this is one dataset"
    owned_tables = results[0]["owned_source_tables"]
    assert len(owned_tables) == 2
    assert owned_datasets[0]["access_request_count"] == 1
    assert len(response_json["dataset_description_change"]) == 1


@pytest.mark.django_db
def test_unpublished_dataset_does_not_return_count(client, user):
    client.force_login(user)
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is one dataset",
        published=False,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="this is another dataset",
        published=False,
    )
    factories.DataSetFactory(
        information_asset_owner=user,
        name="and another",
        published=False,
    )
    response = client.get(reverse(ENDPOINT))
    assert response.status_code == status.HTTP_200_OK
    response_json = response.json()
    results = response_json["results"]
    assert len(results) == 0
"""
