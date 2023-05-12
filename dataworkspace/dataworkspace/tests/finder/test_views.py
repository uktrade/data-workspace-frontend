from urllib.parse import urlencode

import pytest

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from waffle.testutils import override_flag

from dataworkspace.apps.core.models import get_user_model
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.finder.models import DatasetFinderQueryLog
from dataworkspace.tests import factories


@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_default(client, mocker):
    response = client.get(reverse("finder:find_datasets"))

    assert response.status_code == 200
    assert b"Find the datasets which mention for example a particular:" in response.content


@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_with_no_results(client, mocker):
    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.return_value = {
        "took": 11,
        "timed_out": False,
        "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
    }
    response = client.get(reverse("finder:find_datasets"), {"q": "search"})

    assert response.status_code == 200
    assert response.context["results"] == []

    assert b"There are no matches for the phrase" in response.content


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_find_datasets_with_results(staff_client, staff_user, mocker, dataset_finder_db):
    master_dataset = factories.MasterDataSetFactory.create(
        published=True, deleted=False, name="master dataset"
    )
    factories.SourceTableFactory.create(
        dataset=master_dataset,
        schema="public",
        table="data",
        dataset_finder_opted_in=True,
    )

    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.return_value = {
        "took": 11,
        "timed_out": False,
        "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 1260, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
        "aggregations": {
            "indexes": {
                "doc_count_error_upper_bound": 0,
                "sum_other_doc_count": 0,
                "buckets": [
                    {"key": "20210316t070000--public--data--1", "doc_count": 1260},
                ],
            }
        },
    }
    assert DatasetFinderQueryLog.objects.all().count() == 0

    response = staff_client.get(reverse("finder:find_datasets"), {"q": "search"})

    assert response.status_code == 200
    assert len(response.context["results"]) == 1
    result = response.context["results"][0]
    assert result.name == "master dataset"
    assert result.table_matches[0].schema == "public"
    assert result.table_matches[0].table == "data"
    assert result.table_matches[0].count == 1260

    assert DatasetFinderQueryLog.objects.all().count() == 1
    query_log = DatasetFinderQueryLog.objects.all().first()
    assert query_log.query == "search"
    assert query_log.user == staff_user


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
def test_get_results_for_index(access_type, client, mocker, dataset_finder_db):
    source_table = factories.SourceTableFactory.create(
        dataset=factories.MasterDataSetFactory.create(user_access_type=access_type),
        schema="public",
        table="country_stats",
        database=factories.DatabaseFactory(memorable_name="my_database"),
    )
    get_fields = mocker.patch(
        "dataworkspace.apps.finder.elasticsearch.ElasticsearchClient.get_fields"
    )
    get_fields.return_value = ["date", "country", "driving"]
    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.side_effect = [
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1260, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "indexes": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "20210316t070000--public--country_stats--1",
                            "doc_count": 3,
                        },
                    ],
                }
            },
        },
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-13",
                            "driving": 0.0,
                        },
                    },
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-14",
                            "driving": 1.5,
                        },
                    },
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-15",
                            "driving": 6.7,
                        },
                    },
                ],
            },
        },
    ]

    params = {
        "q": "albania",
        "name": "test",
        "uuid": source_table.dataset.id,
        "slug": "slug",
    }
    response = client.post(
        reverse(
            "finder:data_grid_results",
            kwargs={"schema": "public", "table": "country_stats"},
        )
        + "?"
        + urlencode(params),
        {},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "records": [
            {"country": "Albania", "date": "2020-01-13", "driving": 0.0},
            {"country": "Albania", "date": "2020-01-14", "driving": 1.5},
            {"country": "Albania", "date": "2020-01-15", "driving": 6.7},
        ],
    }


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
@override_settings(DATASET_FINDER_SEARCH_RESULTS_PER_PAGE=1)
@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
def test_paging_get_results_for_index(access_type, client, mocker, dataset_finder_db):
    source_table = factories.SourceTableFactory.create(
        dataset=factories.MasterDataSetFactory.create(user_access_type=access_type),
        schema="public",
        table="country_stats",
        database=factories.DatabaseFactory(memorable_name="my_database"),
    )
    get_fields = mocker.patch(
        "dataworkspace.apps.finder.elasticsearch.ElasticsearchClient.get_fields"
    )
    get_fields.return_value = ["date", "country", "driving"]
    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.side_effect = [
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1260, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "indexes": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "20210316t070000--public--country_stats--1",
                            "doc_count": 3,
                        },
                    ],
                }
            },
        },
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-13",
                            "driving": 0.0,
                        },
                    },
                ],
            },
        },
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-14",
                            "driving": 1.5,
                        },
                    },
                ],
            },
        },
    ]

    params = {
        "q": "albania",
        "name": "test",
        "uuid": source_table.dataset.id,
        "slug": "slug",
    }
    response = client.post(
        reverse(
            "finder:data_grid_results",
            kwargs={"schema": "public", "table": "country_stats"},
        )
        + "?"
        + urlencode(params),
        {"limit": 1, "start": 1},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "records": [{"country": "Albania", "date": "2020-01-13", "driving": 0.0}],
    }


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_download_all_results(client, mocker, dataset_finder_db):
    source_table = factories.SourceTableFactory.create(
        dataset=factories.MasterDataSetFactory.create(user_access_type=UserAccessType.OPEN),
        schema="public",
        table="country_stats",
        database=factories.DatabaseFactory(memorable_name="my_database"),
    )
    get_fields = mocker.patch(
        "dataworkspace.apps.finder.elasticsearch.ElasticsearchClient.get_fields"
    )
    get_fields.return_value = ["date", "country", "driving"]
    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.side_effect = [
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1260, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "indexes": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "20210316t070000--public--country_stats--1",
                            "doc_count": 3,
                        },
                    ],
                }
            },
        },
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-13",
                            "driving": 0.0,
                        },
                    },
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Algeria",
                            "date": "2020-01-14",
                            "driving": 1.5,
                        },
                    },
                ],
            },
        },
    ]

    params = {
        "q": "albania",
        "name": "test",
        "uuid": source_table.dataset.id,
        "slug": "slug",
        "download": "1",
    }

    response = client.post(
        reverse(
            "finder:data_grid_results",
            kwargs={"schema": "public", "table": "country_stats"},
        )
        + "?"
        + urlencode(params),
        {"columns": ["country", "date", "driving"], "filters": {}},
    )

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == (
        b'"country","date","driving"\r\n"Albania","2020-01-13",0.0\r\n"Algeria","2020-01-14",1.5\r\n'
    )


@pytest.mark.django_db(transaction=True)
@override_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG, active=True)
def test_download_filtered_columns(client, mocker, dataset_finder_db):
    source_table = factories.SourceTableFactory.create(
        dataset=factories.MasterDataSetFactory.create(user_access_type=UserAccessType.OPEN),
        schema="public",
        table="country_stats",
        database=factories.DatabaseFactory(memorable_name="my_database"),
    )
    get_fields = mocker.patch(
        "dataworkspace.apps.finder.elasticsearch.ElasticsearchClient.get_fields"
    )
    get_fields.return_value = ["date", "country", "driving"]
    dataset_search = mocker.patch("elasticsearch.Elasticsearch.search")
    dataset_search.side_effect = [
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 45, "successful": 45, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1260, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "indexes": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "20210316t070000--public--country_stats--1",
                            "doc_count": 3,
                        },
                    ],
                }
            },
        },
        {
            "took": 11,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Albania",
                            "date": "2020-01-13",
                            "driving": 0.0,
                        },
                    },
                    {
                        "_index": "20210316t070000--public--country_stats--1",
                        "_type": "_doc",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "country": "Algeria",
                            "date": "2020-01-14",
                            "driving": 1.5,
                        },
                    },
                ],
            },
        },
    ]

    params = {
        "q": "albania",
        "name": "test",
        "uuid": source_table.dataset.id,
        "slug": "slug",
        "download": "1",
    }

    response = client.post(
        reverse(
            "finder:data_grid_results",
            kwargs={"schema": "public", "table": "country_stats"},
        )
        + "?"
        + urlencode(params),
        {"columns": ["country"], "filters": {}},
    )

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == (b'"country"\r\n"Albania"\r\n"Algeria"\r\n')
