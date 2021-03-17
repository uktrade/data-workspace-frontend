import pytest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from waffle.testutils import override_flag

from django.test import Client
from dataworkspace.apps.finder.models import DatasetFinderQueryLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_default(client, mocker):
    response = client.get(reverse('finder:find_datasets'))

    assert response.status_code == 200
    assert b"Search for master datasets in Data Workspace" in response.content


@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_with_no_results(client, mocker):
    dataset_search = mocker.patch('elasticsearch.Elasticsearch.search')
    dataset_search.return_value = {
        'took': 11,
        'timed_out': False,
        '_shards': {'total': 45, 'successful': 45, 'skipped': 0, 'failed': 0},
        'hits': {
            'total': {'value': 0, 'relation': 'eq'},
            'max_score': None,
            'hits': [],
        },
    }
    response = client.get(reverse('finder:find_datasets'), {"q": "search"})

    assert response.status_code == 200
    assert response.context["results"] == []

    assert b"There are no matches for the phrase" in response.content


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_with_results(client, mocker, dataset_finder_db):
    master_dataset = factories.MasterDataSetFactory.create(
        published=True, deleted=False, name="master dataset"
    )
    factories.SourceTableFactory.create(
        dataset=master_dataset,
        schema='public',
        table='data',
        dataset_finder_opted_in=True,
    )

    dataset_search = mocker.patch('elasticsearch.Elasticsearch.search')
    dataset_search.return_value = {
        'took': 11,
        'timed_out': False,
        '_shards': {'total': 45, 'successful': 45, 'skipped': 0, 'failed': 0},
        'hits': {
            'total': {'value': 1260, 'relation': 'eq'},
            'max_score': None,
            'hits': [],
        },
        'aggregations': {
            'indexes': {
                'doc_count_error_upper_bound': 0,
                'sum_other_doc_count': 0,
                'buckets': [
                    {'key': '20210316t070000--public--data--1', 'doc_count': 1260},
                ],
            }
        },
    }
    assert DatasetFinderQueryLog.objects.all().count() == 0

    response = client.get(reverse('finder:find_datasets'), {"q": "search"})

    assert response.status_code == 200
    assert len(response.context["results"]) == 1
    result = response.context["results"][0]
    assert result.name == 'master dataset'
    assert result.table_matches[0].schema == 'public'
    assert result.table_matches[0].table == 'data'
    assert result.table_matches[0].count == 1260

    assert DatasetFinderQueryLog.objects.all().count() == 1
    query_log = DatasetFinderQueryLog.objects.all().first()
    assert query_log.query == 'search'
    assert query_log.user == user


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_search_in_data_explorer(client, mocker, dataset_finder_db):
    master_dataset = factories.MasterDataSetFactory()
    factories.SourceTableFactory(dataset=master_dataset, schema='public', table='data')

    response = client.get(
        reverse(
            'finder:search_in_data_explorer',
            kwargs={'schema': 'public', 'table': 'data'},
        ),
        {"q": "search"},
    )

    assert response.status_code == 302
    assert reverse('explorer:index') in response['Location']
