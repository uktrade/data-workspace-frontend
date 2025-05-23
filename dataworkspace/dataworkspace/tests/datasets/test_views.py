import json
import random
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import faker
import mock
import psycopg2
import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import CharField, Value
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from freezegun import freeze_time
from lxml import html
from waffle.testutils import override_flag

from dataworkspace.apps.accounts.models import UserDataTableView
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.storage import ClamAVResponse
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
    VisualisationUserPermission,
)
from dataworkspace.apps.datasets.search import _get_datasets_data_for_user_matching_query
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.your_files.models import UploadedTable
from dataworkspace.tests import factories
from dataworkspace.tests.common import MatchUnorderedMembers, get_http_sso_data
from dataworkspace.tests.conftest import get_client, get_user_data
from dataworkspace.tests.factories import (
    AccessRequestFactory,
    UserFactory,
    VisualisationCatalogueItemFactory,
    VisualisationLinkFactory,
    VisualisationUserPermissionFactory,
)


def test_eligibility_criteria_list(client):
    ds = factories.DataSetFactory.create(
        eligibility_criteria=["Criteria 1", "Criteria 2"], published=True
    )

    response = client.get(reverse("datasets:eligibility_criteria", kwargs={"dataset_uuid": ds.id}))

    assert response.status_code == 200
    assert "Criteria 1" in str(response.content)
    assert "Criteria 2" in str(response.content)


@pytest.mark.parametrize(
    "meet_criteria,redirect_view",
    [
        ("yes", "request_access:dataset"),
        ("no", "datasets:eligibility_criteria_not_met"),
    ],
)
def test_submit_eligibility_criteria(client, test_case, meet_criteria, redirect_view):
    ds = factories.DataSetFactory.create(
        eligibility_criteria=["Criteria 1", "Criteria 3"], published=True
    )

    response = client.post(
        reverse("datasets:eligibility_criteria", kwargs={"dataset_uuid": ds.id}),
        data={"meet_criteria": meet_criteria},
        follow=True,
    )

    test_case.assertRedirects(response, reverse(redirect_view, kwargs={"dataset_uuid": ds.id}))


@pytest.mark.django_db
def test_toggle_bookmark_on_dataset():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.DataSetFactory.create(published=True)

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is True


@pytest.mark.django_db
def test_toggle_bookmark_off_dataset():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.DataSetFactory.create(published=True)
    factories.DataSetBookmarkFactory.create(user=user, dataset=ds)
    assert ds.user_has_bookmarked(user) is True

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is False


@pytest.mark.django_db
def test_set_bookmark():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.DataSetFactory.create(published=True)

    response = client.post(
        reverse("datasets:set_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    # Called from JavaScript - no need for redirect
    assert response.status_code == 200

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is True


@pytest.mark.django_db
def test_unset_bookmark():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.DataSetFactory.create(published=True)
    factories.DataSetBookmarkFactory.create(user=user, dataset=ds)
    assert ds.user_has_bookmarked(user) is True

    response = client.post(
        reverse("datasets:unset_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    # Called from JavaScript - no need for redirect
    assert response.status_code == 200

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is False


@pytest.mark.django_db
def test_toggle_bookmark_on_reference():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.ReferenceDatasetFactory.create(published=True)

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.uuid}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is True


@pytest.mark.django_db
def test_toggle_bookmark_off_reference():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.ReferenceDatasetFactory.create(published=True)
    factories.ReferenceDataSetBookmarkFactory.create(user=user, reference_dataset=ds)
    assert ds.user_has_bookmarked(user) is True

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.uuid}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is False


@pytest.mark.django_db
def test_toggle_bookmark_on_visualisation():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.VisualisationCatalogueItemFactory.create(published=True)

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is True


@pytest.mark.django_db
def test_toggle_bookmark_off_visualisation():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    ds = factories.VisualisationCatalogueItemFactory.create(published=True)
    factories.VisualisationBookmarkFactory.create(user=user, visualisation=ds)
    assert ds.user_has_bookmarked(user) is True

    response = client.get(
        reverse("datasets:toggle_bookmark", kwargs={"dataset_uuid": ds.id}),
    )
    assert response.status_code == 302

    ds.refresh_from_db()
    assert ds.user_has_bookmarked(user) is False


def test_find_datasets_with_no_results(client):
    response = client.get(reverse("datasets:find_datasets"), {"q": "search"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == []

    assert b"There are no results for your search" in response.content


def test_find_datasets_has_search_result_count_span_for_live_search_and_gtm(client):
    response = client.get(reverse("datasets:find_datasets"))

    assert response.status_code == 200
    doc = html.fromstring(response.content.decode(response.charset))

    elem = doc.xpath('//*[@id="search-results-count"]')
    assert (
        len(elem) == 1
    ), "There must be a node with the 'search-results-count' id for live search/GTM to work correctly."
    assert elem[0].text.isnumeric(), "The contents of the node should be numeric only"

    assert "role" in elem[0].keys()
    assert elem[0].get("role") == "status"


def expected_search_result(catalogue_item, **kwargs):
    result = {
        "id": getattr(catalogue_item, "uuid", catalogue_item.id),
        "name": catalogue_item.name,
        "slug": catalogue_item.slug,
        "search_rank": mock.ANY,
        "search_rank_name": mock.ANY,
        "search_rank_short_description": mock.ANY,
        "search_rank_tags": mock.ANY,
        "search_rank_description": mock.ANY,
        "short_description": catalogue_item.short_description,
        "published_date": mock.ANY,
        "source_tag_ids": mock.ANY,
        "topic_tag_ids": mock.ANY,
        "publisher_tag_ids": mock.ANY,
        "data_type": mock.ANY,
        "published": catalogue_item.published,
        "has_access": True,
        "publishers": mock.ANY,
        "is_bookmarked": False,
        "table_match": False,
        "is_subscribed": False,
        "is_open_data": getattr(catalogue_item, "user_access_type", None) == UserAccessType.OPEN,
        "sources": mock.ANY,
        "topics": mock.ANY,
        "last_updated": mock.ANY,
        "average_unique_users_daily": mock.ANY,
        "is_owner": False,
        "is_contact": False,
        "is_editor": False,
    }
    result.update(**kwargs)
    return result


def test_find_datasets_combines_results(client):
    factories.DataSetFactory.create(published=False, name="Unpublished search dataset")
    ds = factories.DataSetFactory.create(published=True, name="A search dataset")
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name="A search reference dataset"
    )
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A search visualisation"
    )

    response = client.get(reverse("datasets:find_datasets"), {"q": "search"})

    assert response.status_code == 200
    assert len(list(response.context["datasets"])) == 3
    datasets = list(response.context["datasets"])

    expected_results = [
        expected_search_result(ds, has_access=False, data_type=DataSetType.DATACUT),
        expected_search_result(rds, data_type=DataSetType.REFERENCE),
        expected_search_result(vis, data_type=DataSetType.VISUALISATION, has_access=False),
    ]

    for expected in expected_results:
        assert expected in datasets

    assert "If you haven’t found what you’re looking for" in response.content.decode(
        response.charset
    )


def test_find_datasets_by_source_table_name(client, dataset_db):
    ds = factories.DataSetFactory.create(
        published=True, name="A search dataset", type=DataSetType.MASTER
    )
    factories.SourceTableFactory.create(
        dataset=ds,
        schema="public",
        table="dataset_test",
        database=factories.DatabaseFactory.create(memorable_name="my_database"),
    )
    ref_ds = factories.ReferenceDatasetFactory.create()

    # Source dataset: table name only
    response = client.get(reverse("datasets:find_datasets"), {"q": "dataset_test"})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds, has_access=False, table_match=True, data_type=DataSetType.MASTER
        ),
    ]
    # Source dataset: schema and table
    response = client.get(reverse("datasets:find_datasets"), {"q": "public.dataset_test"})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds, has_access=False, table_match=True, data_type=DataSetType.MASTER
        ),
    ]
    # Reference dataset: table
    response = client.get(reverse("datasets:find_datasets"), {"q": ref_ds.table_name})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ref_ds, table_match=True, data_type=DataSetType.REFERENCE),
    ]


def test_find_datasets_by_source_table_does_exact_match_only(client):
    ds = factories.DataSetFactory.create(
        published=True, name="A search dataset", type=DataSetType.MASTER
    )
    factories.SourceTableFactory.create(
        dataset=ds,
        schema="public",
        table="dataset_test",
        database=factories.DatabaseFactory.create(memorable_name="my_database"),
    )
    response = client.get(reverse("datasets:find_datasets"), {"q": "_test"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == []


def test_find_datasets_by_source_table_falls_back_to_normal_search(client):
    ds = factories.DataSetFactory.create(
        published=True, name="A search dataset", type=DataSetType.MASTER
    )
    factories.SourceTableFactory.create(
        dataset=ds,
        schema="public",
        table="dataset_test",
        database=factories.DatabaseFactory.create(memorable_name="my_database"),
    )
    response = client.get(reverse("datasets:find_datasets"), {"q": "dataset"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ds, has_access=False, data_type=DataSetType.MASTER),
    ]


def test_find_datasets_does_not_show_deleted_entries(client, staff_client):
    factories.DataSetFactory.create(
        deleted=True, published=True, name="Unpublished search dataset"
    )
    factories.DataSetFactory.create(deleted=True, published=True, name="A search dataset")
    factories.ReferenceDatasetFactory.create(
        deleted=True, published=True, name="A search reference dataset"
    )
    factories.VisualisationCatalogueItemFactory.create(
        deleted=True, published=True, name="A search visualisation"
    )

    response = client.get(reverse("datasets:find_datasets"))
    staff_response = staff_client.get(reverse("datasets:find_datasets"))

    assert response.status_code == 200
    assert list(response.context["datasets"]) == []

    assert staff_response.status_code == 200
    assert list(staff_response.context["datasets"]) == []


def test_find_datasets_filters_by_query(client):
    factories.DataSetFactory.create(published=True, name="A dataset")
    factories.ReferenceDatasetFactory.create(published=True, name="A reference dataset")
    factories.VisualisationCatalogueItemFactory.create(published=True, name="A visualisation")

    ds = factories.DataSetFactory.create(published=True, name="A new dataset")
    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A new visualisation"
    )

    response = client.get(reverse("datasets:find_datasets"), {"q": "new"})

    assert response.status_code == 200

    results = list(response.context["datasets"])
    expected_search_results = [
        expected_search_result(ds, data_type=ds.type, has_access=False),
        expected_search_result(
            rds,
            data_type=DataSetType.REFERENCE,
        ),
        expected_search_result(vis, data_type=DataSetType.VISUALISATION, has_access=False),
    ]

    assert len(results) == 3
    for expected in expected_search_results:
        assert expected in results


def test_find_datasets_filters_by_query_acronym(client):
    factories.DataSetFactory.create(published=True, name="A dataset")
    factories.ReferenceDatasetFactory.create(published=True, name="A reference dataset")
    factories.VisualisationCatalogueItemFactory.create(published=True, name="A visualisation")

    ds = factories.DataSetFactory.create(published=True, description="testing EW acronym")

    assert ds.acronyms == "export wins"

    response = client.get(reverse("datasets:find_datasets"), {"q": "export wins"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ds, data_type=ds.type, has_access=False),
    ]


def test_find_datasets_filters_by_data_type(client):
    factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    ds = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")

    response = client.get(reverse("datasets:find_datasets"), {"data_type": [DataSetType.DATACUT]})

    assert response.status_code == 200

    expected_results = [
        expected_search_result(ds, has_access=False),
    ]

    datasets = list(response.context["datasets"])

    assert len(datasets) == 1

    for i, ds in enumerate(datasets):
        expected = expected_results[i]
        assert ds == expected


def test_find_datasets_filters_visualisations_by_data_type(client):
    factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    ds = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A new visualisation"
    )

    response = client.get(reverse("datasets:find_datasets"), {"data_type": [2, 3]})

    assert response.status_code == 200
    expected_results = [
        expected_search_result(ds, has_access=False),
        expected_search_result(vis, data_type=DataSetType.VISUALISATION, has_access=False),
    ]

    results = list(response.context["datasets"])
    assert len(results) == 2

    for expected in expected_results:
        assert expected in results


def test_find_datasets_filters_by_source(client):
    source = factories.SourceTagFactory()
    source_2 = factories.SourceTagFactory()
    # Create another SourceTag that won't be associated to a dataset
    factories.SourceTagFactory()

    _ds = factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    _ds.tags.set([factories.SourceTagFactory()])

    _vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A visualisation"
    )

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=_vis.visualisation_template, dataset=_ds
    )

    ds = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    ds.tags.set([source, source_2])

    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    rds.tags.set([source])

    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A new visualisation"
    )
    vis.tags.set([source])

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=vis.visualisation_template, dataset=ds
    )

    response = client.get(reverse("datasets:find_datasets"), {"source": [source.id]})

    assert response.status_code == 200
    results = list(response.context["datasets"])
    expected_results = [
        expected_search_result(
            ds,
            has_access=False,
            source_tag_ids=MatchUnorderedMembers([source.id, source_2.id]),
        ),
        expected_search_result(rds, source_tag_ids=[source.id]),
        expected_search_result(
            vis,
            source_tag_ids=[source.id],
            has_access=False,
            data_type=DataSetType.VISUALISATION,
        ),
    ]

    assert len(results) == 3
    assert len(list(response.context["form"].fields["source"].choices)) == 3

    for expected in expected_results:
        assert expected in results


def test_find_datasets_filters_by_topic(client):
    topic = factories.TopicTagFactory.create()
    topic_2 = factories.TopicTagFactory.create()
    # Create another SourceTag that won't be associated to a dataset
    factories.TopicTagFactory.create()

    _ds = factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    _ds.tags.set([factories.SourceTagFactory()])

    _vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A visualisation"
    )

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=_vis.visualisation_template, dataset=_ds
    )

    ds = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    ds.tags.set([topic, topic_2])

    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    rds.tags.set([topic])

    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A new visualisation"
    )
    vis.tags.set([topic])

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=vis.visualisation_template, dataset=ds
    )

    response = client.get(reverse("datasets:find_datasets"), {"topic": [topic.id]})

    assert response.status_code == 200
    results = list(response.context["datasets"])
    expected_results = [
        expected_search_result(
            ds,
            has_access=False,
            topic_tag_ids=MatchUnorderedMembers([topic.id, topic_2.id]),
            search_rank=0.0,
        ),
        expected_search_result(
            rds,
            topic_tag_ids=[topic.id],
            data_type=DataSetType.REFERENCE,
        ),
        expected_search_result(
            vis,
            has_access=False,
            topic_tag_ids=[topic.id],
            data_type=DataSetType.VISUALISATION,
        ),
    ]

    assert len(list(response.context["form"].fields["topic"].choices)) == 2
    assert len(results) == 3
    for expected in expected_results:
        assert expected in results


def test_find_datasets_filters_by_publisher(client):
    publisher = factories.PublisherTagFactory.create()
    publisher_2 = factories.PublisherTagFactory.create()
    # Create another SourceTag that won't be associated to a dataset
    factories.PublisherTagFactory.create()

    _ds = factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    _ds.tags.set([factories.SourceTagFactory()])

    _vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A visualisation"
    )

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=_vis.visualisation_template, dataset=_ds
    )

    ds = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    ds.tags.set([publisher, publisher_2])

    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    rds.tags.set([publisher])

    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A new visualisation"
    )
    vis.tags.set([publisher])

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=vis.visualisation_template, dataset=ds
    )

    response = client.get(reverse("datasets:find_datasets"), {"publisher": [publisher.id]})

    assert response.status_code == 200
    results = list(response.context["datasets"])
    expected_results = [
        expected_search_result(
            ds,
            has_access=False,
            publisher_tag_ids=MatchUnorderedMembers([publisher.id, publisher_2.id]),
            search_rank=0.0,
        ),
        expected_search_result(
            rds,
            publisher_tag_ids=[publisher.id],
            data_type=DataSetType.REFERENCE,
        ),
        expected_search_result(
            vis,
            has_access=False,
            publisher_tag_ids=[publisher.id],
            data_type=DataSetType.VISUALISATION,
        ),
    ]

    assert len(list(response.context["form"].fields["publisher"].choices)) == 2
    assert len(results) == 3
    for expected in expected_results:
        assert expected in results


@pytest.mark.parametrize(
    "sort_field",
    ("alphabetical",),
)
def test_find_datasets_order_by_name_asc(sort_field, client):
    ds1 = factories.DataSetFactory.create(name="a dataset")
    rds = factories.ReferenceDatasetFactory.create(name="b reference dataset")
    vis = factories.VisualisationCatalogueItemFactory.create(name="c visualisation")

    response = client.get(reverse("datasets:find_datasets"), {"sort": sort_field})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ds1, has_access=False),
        expected_search_result(rds, data_type=DataSetType.REFERENCE),
        expected_search_result(vis, data_type=DataSetType.VISUALISATION, has_access=False),
    ]


@pytest.mark.parametrize(
    "sort_field",
    ("-published",),
)
def test_find_datasets_order_by_newest_first(sort_field, client):
    ads1 = factories.DataSetFactory.create(published_at=date.today())
    ads2 = factories.DataSetFactory.create(published_at=date.today() - timedelta(days=3))
    ads3 = factories.DataSetFactory.create(published_at=date.today() - timedelta(days=4))

    response = client.get(reverse("datasets:find_datasets"), {"sort": sort_field})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ads1, data_type=ads1.type, has_access=False),
        expected_search_result(ads2, has_access=False),
        expected_search_result(ads3, has_access=False),
    ]


@pytest.mark.parametrize(
    "sort_field",
    ("published",),
)
def test_find_datasets_order_by_oldest_first(sort_field, client):
    ads1 = factories.DataSetFactory.create(published_at=date.today() - timedelta(days=1))
    ads2 = factories.DataSetFactory.create(published_at=date.today() - timedelta(days=2))
    ads3 = factories.DataSetFactory.create(published_at=date.today() - timedelta(days=3))

    response = client.get(reverse("datasets:find_datasets"), {"sort": sort_field})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ads3, has_access=False, data_type=ads3.type),
        expected_search_result(ads2, has_access=False, data_type=ads2.type),
        expected_search_result(ads1, has_access=False, data_type=ads1.type),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sort_field",
    ("relevance",),
)
def test_find_datasets_order_by_relevance_prioritises_bookmarked_datasets(sort_field):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    bookmarked_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master bookmarked",
    )
    factories.DataSetBookmarkFactory.create(user=user, dataset=bookmarked_master)
    unbookmarked_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master",
    )

    # If there is no search query, then if sorting by relevance, the default, datasets
    # bookmarked by the current user are most likely to be relevant, and so should be
    # at the top
    sort = ("relevance",)
    response = client.get(reverse("datasets:find_datasets"), {"sort": sort})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(bookmarked_master, has_access=False, is_bookmarked=True),
        expected_search_result(unbookmarked_master, has_access=False),
    ]

    # If there is a search query, and sorting by relevance, the bookmarked state of
    # datasets should not be taken into account, since the user has probably just seen
    # their bookmarks on the front page and they weren't helpful. In this case both
    # dataset names match the search query, but the extra word in bookmarked_master
    # means the normalisation on length makes it treated as less relevant
    sort = ("relevance",)
    response = client.get(reverse("datasets:find_datasets"), {"sort": sort, "q": "master"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(unbookmarked_master, has_access=False),
        expected_search_result(bookmarked_master, has_access=False, is_bookmarked=True),
    ]


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
def test_datasets_and_visualisations_doesnt_return_duplicate_results(access_type, staff_client):
    normal_user = get_user_model().objects.create(
        username="bob.user@test.com", is_staff=False, is_superuser=False, email="bob.user@test.com"
    )
    staff_user = get_user_model().objects.create(
        username="bob.staff@test.com", is_staff=True, is_superuser=True, email="bob.staff@test.com"
    )

    users = [factories.UserFactory.create() for _ in range(3)]
    source_tags = [factories.SourceTagFactory.create() for _ in range(5)]
    topic_tags = [factories.TopicTagFactory.create() for _ in range(5)]

    master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="A master",
        user_access_type=access_type,
    )
    master2 = factories.DataSetFactory.create(
        published=False,
        type=DataSetType.MASTER,
        name="A master",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    datacut = factories.DataSetFactory.create(
        published=False,
        type=DataSetType.DATACUT,
        name="A datacut",
        user_access_type=access_type,
    )
    datacut2 = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="A datacut",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    visualisation = factories.VisualisationCatalogueItemFactory.create(
        published=True, name="A visualisation"
    )

    for user in users + [normal_user, staff_user]:
        factories.DataSetUserPermissionFactory.create(dataset=master, user=user)
        master.tags.set(random.sample(source_tags, 3) + random.sample(topic_tags, 3))
        factories.DataSetUserPermissionFactory.create(dataset=master2, user=user)
        master2.tags.set(random.sample(source_tags, 3) + random.sample(topic_tags, 3))

        factories.DataSetUserPermissionFactory.create(dataset=datacut, user=user)
        datacut.tags.set(random.sample(source_tags, 3) + random.sample(topic_tags, 3))
        factories.DataSetUserPermissionFactory.create(dataset=datacut2, user=user)
        datacut2.tags.set(random.sample(source_tags, 3) + random.sample(topic_tags, 3))

        factories.VisualisationUserPermissionFactory.create(visualisation=visualisation, user=user)

    for u in [normal_user, staff_user]:
        datasets = _get_datasets_data_for_user_matching_query(
            DataSet.objects.live(), query="", id_field="id", user=u
        )
        assert len(datasets) == len(set(dataset["id"] for dataset in datasets))

        references = _get_datasets_data_for_user_matching_query(
            ReferenceDataset.objects.live().annotate(
                data_catalogue_editors=Value(None, output_field=CharField())
            ),
            "",
            id_field="uuid",
            user=u,
        )
        assert len(references) == len(set(reference["uuid"] for reference in references))

        visualisations = _get_datasets_data_for_user_matching_query(
            VisualisationCatalogueItem.objects, query="", id_field="id", user=u
        )
        assert len(visualisations) == len(
            set(visualisation["id"] for visualisation in visualisations)
        )


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_find_datasets_filters_by_access_requires_authenticate(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    user2 = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    public_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - public",
        user_access_type=access_type,
    )
    factories.DataSetUserPermissionFactory.create(user=user2, dataset=public_master)
    response = client.get(reverse("datasets:find_datasets"), {"status": ["access"]})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [expected_search_result(public_master)]


@pytest.mark.django_db
def test_find_datasets_filters_by_bookmark_single():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    bookmarked_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.DataSetBookmarkFactory.create(user=user, dataset=bookmarked_master)

    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "bookmarked"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(bookmarked_master, has_access=False, is_bookmarked=True)
    ]


@pytest.mark.django_db
def test_find_datasets_filter_by_subscription():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    master_dataset = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master subscribed",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.DataSetSubscriptionFactory.create(user=user, dataset=master_dataset)

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.ReferenceDatasetFactory.create(published=True, name="Reference - public")

    factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )

    response = client.get(reverse("datasets:find_datasets") + "?my_datasets=subscribed")

    assert response.status_code == 200
    results = list(response.context["datasets"])
    assert len(results) == 1


@pytest.mark.django_db
def test_find_datasets_filters_by_bookmark_master():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    bookmarked_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.DataSetBookmarkFactory.create(user=user, dataset=bookmarked_master)

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.ReferenceDatasetFactory.create(published=True, name="Reference - public")

    factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )

    response = client.get(reverse("datasets:find_datasets") + "?my_datasets=bookmarked")

    assert response.status_code == 200

    results = list(response.context["datasets"])
    # assert len(results) == 1

    assert results[0] == expected_search_result(
        bookmarked_master, has_access=False, is_bookmarked=True
    )


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_find_datasets_filters_by_bookmark_reference(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - public",
        user_access_type=access_type,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - open",
        user_access_type=UserAccessType.OPEN,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    public_reference = factories.ReferenceDatasetFactory.create(
        published=True, name="Reference - public"
    )
    factories.ReferenceDataSetBookmarkFactory.create(user=user, reference_dataset=public_reference)

    factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=access_type,
    )

    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "bookmarked"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            public_reference,
            is_bookmarked=True,
            data_type=DataSetType.REFERENCE,
        )
    ]


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_find_datasets_filters_by_bookmark_visualisation(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - public",
        user_access_type=access_type,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - open",
        user_access_type=UserAccessType.OPEN,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.ReferenceDatasetFactory.create(published=True, name="Reference - public")

    public_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=access_type,
    )
    factories.VisualisationBookmarkFactory.create(user=user, visualisation=public_vis)

    # response = client.get(reverse('datasets:find_datasets'), {"status": ["bookmark"]})
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "bookmarked"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(public_vis, is_bookmarked=True, data_type=DataSetType.VISUALISATION)
    ]


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_find_datasets_filters_by_bookmark_datacut(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - public",
        user_access_type=access_type,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - open",
        user_access_type=UserAccessType.OPEN,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    public_datacut = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.DataSetBookmarkFactory.create(user=user, dataset=public_datacut)

    factories.ReferenceDatasetFactory.create(published=True, name="Reference - public")

    factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=access_type,
    )

    # response = client.get(reverse('datasets:find_datasets'), {"status": ["bookmark"]})
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "bookmarked"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            public_datacut,
            data_type=DataSetType.DATACUT,
            is_bookmarked=True,
            has_access=False,
        )
    ]


@pytest.mark.django_db
def test_find_datasets_filters_by_show_unpublished():
    user = factories.UserFactory.create(is_superuser=True)
    client = Client(**get_http_sso_data(user))

    published_master = factories.DataSetFactory.create(name="published dataset")
    unpublished_master = factories.DataSetFactory.create(
        published=False, name="unpublished dataset"
    )

    response = client.get(reverse("datasets:find_datasets"))

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(published_master, has_access=mock.ANY)
    ]

    response = client.get(reverse("datasets:find_datasets"), {"admin_filters": "unpublished"})

    assert response.status_code == 200
    expected_results = [
        expected_search_result(published_master, has_access=mock.ANY),
        expected_search_result(unpublished_master, has_access=mock.ANY),
    ]

    results = list(response.context["datasets"])

    assert len(results) == 2
    for expected in expected_results:
        assert expected in results


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_find_datasets_filters_by_access_and_use_only_returns_the_dataset_once(
    access_type,
):
    """Meant to prevent a regression where the combination of these two filters would return datasets multiple times
    based on the number of users with permissions to see that dataset, but the dataset didn't actually require any
    permission to use."""
    user = factories.UserFactory.create(is_superuser=False)
    user2 = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    access_granted_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access redundantly granted",
        user_access_type=access_type,
    )
    factories.DataSetUserPermissionFactory.create(user=user, dataset=access_granted_master)
    factories.DataSetUserPermissionFactory.create(user=user2, dataset=access_granted_master)

    response = client.get(
        reverse("datasets:find_datasets"),
        {"access": "yes", "use": str(DataSetType.MASTER)},
    )

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [expected_search_result(access_granted_master)]


@pytest.mark.django_db
def test_find_datasets_filters_by_enquires_contact(user, client):
    ds1 = factories.DataSetFactory.create(
        name="Dataset",
        enquiries_contact=user,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    ds2 = factories.ReferenceDatasetFactory.create(name="Reference")
    ds3 = factories.VisualisationCatalogueItemFactory.create(
        name="Visualisation", user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
    )

    response = client.get(reverse("datasets:find_datasets"))
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ds1, is_contact=True),
        expected_search_result(ds2),
        expected_search_result(ds3),
    ]


@pytest.mark.django_db
def test_find_datasets_filters_by_editor(user, client):
    ds1 = factories.DataSetFactory.create(
        name="Dataset",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    ds1.data_catalogue_editors.add(user)

    ds2 = factories.ReferenceDatasetFactory.create(name="Reference")
    ds3 = factories.VisualisationCatalogueItemFactory.create(
        name="Visualisation", user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
    )

    response = client.get(reverse("datasets:find_datasets"))
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(ds1, is_editor=True),
        expected_search_result(ds2),
        expected_search_result(ds3),
    ]


@pytest.mark.django_db
def test_find_datasets_filters_by_asset_ownership(user, client):
    ds1 = factories.DataSetFactory.create(
        name="Dataset",
        information_asset_manager=user,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    ds2 = factories.ReferenceDatasetFactory.create(name="Reference")
    ds3 = factories.VisualisationCatalogueItemFactory.create(
        name="Visualisation", user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
    )

    # All available datasets
    response = client.get(reverse("datasets:find_datasets"))
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
        expected_search_result(ds2),
        expected_search_result(ds3),
    ]

    # User is IAM
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "owned"})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
    ]

    # User is IAO
    ds3.information_asset_owner = user
    ds3.save()
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "owned"})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
        expected_search_result(
            ds3,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
    ]

    # User is IAM and IAO
    ds1.information_asset_owner = user
    ds1.save()
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "owned"})
    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
        expected_search_result(
            ds3,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
    ]


@pytest.mark.django_db
def test_shows_data_insights_on_datasets_and_datacuts_for_owners_and_managers(user, client):
    dataset = factories.DataSetFactory.create(
        name="Dataset",
        information_asset_owner=user,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    dataset2 = factories.DataSetFactory.create(
        name="Dataset2",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    datacut = factories.DataSetFactory.create(
        name="Datacut",
        type=DataSetType.DATACUT,
        information_asset_owner=user,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    datacut2 = factories.DataSetFactory.create(
        name="Datacut2",
        type=DataSetType.DATACUT,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    refdataset = factories.ReferenceDatasetFactory.create(name="ReferenceDataset")
    visualisation = factories.VisualisationCatalogueItemFactory.create(
        name="VisualisationCatalogueItem",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )

    # Only shows on owned dataset or datacut
    dataset_search_responses = client.get(reverse("datasets:find_datasets"))
    assert dataset_search_responses.status_code == 200

    datasets = [
        expected_search_result(
            dataset,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
        expected_search_result(dataset2),
        expected_search_result(
            datacut,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=False,
        ),
        expected_search_result(datacut2),
        expected_search_result(refdataset),
        expected_search_result(visualisation),
    ]
    for dataset in datasets:
        assert dataset in dataset_search_responses.context["datasets"]


@mock.patch("dataworkspace.apps.datasets.views.show_pipeline_failed_message_on_dataset")
@pytest.mark.django_db
def test_pipeline_failure_message_shows_on_data_insights(
    mock_show_pipeline_failed_message_on_dataset, user, client
):
    dataset = factories.DataSetFactory.create(
        name="Dataset",
        information_asset_owner=user,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )

    # Only shows pipeline error on owned datasets
    mock_show_pipeline_failed_message_on_dataset._mock_return_value = True
    response = client.get(reverse("datasets:find_datasets"))
    assert response.status_code == 200

    datasets = [
        expected_search_result(
            dataset,
            is_owner=True,
            number_of_requests=mock.ANY,
            count=mock.ANY,
            source_tables_amount=mock.ANY,
            filled_dicts=mock.ANY,
            show_pipeline_failed_message=True,
        ),
    ]
    for dataset in datasets:
        assert dataset in response.context["datasets"]
    soup = BeautifulSoup(response.content.decode(response.charset))
    assert "One or more tables failed to update" in soup.find("dd", class_="error-message")


@mock.patch("dataworkspace.apps.datasets.views.log_permission_change")
@pytest.mark.django_db
class TestDescriptionChangeEventLog(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.description = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla ex ex, vulputate vel condimentum a, ornare quis felis. Proin ut bibendum arcu. Donec a ligula eros. Mauris pellentesque nisi eu."  # pylint: disable=line-too-long
        self.new_description = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam fringilla non ante et lobortis. Nam mollis sagittis facilisis. Nam suscipit, leo et condimentum sagittis, dolor risus bibendum massa, a luctus mauris."  # pylint: disable=line-too-long
        self.dataset = factories.DataSetFactory.create(
            name="Dataset",
            information_asset_owner=self.user,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            description=self.description,
        )
        self.visualisation = factories.VisualisationCatalogueItemFactory.create(
            name="VisualisationCatalogueItem",
            information_asset_owner=self.user,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            description=self.description,
        )

    def test_eventlog_runs_when_dataset_description_changed(self, mock_log_permission_change):
        response = self.client.post(
            reverse("datasets:edit_dataset", args=(self.dataset.id,)),
            data={
                "name": self.dataset.name,
                "short_description": "test",
                "government_security_classification": 2,
                "description": self.new_description,
            },
        )
        assert response.status_code == 302
        mock_log_permission_change.assert_called_with(
            self.user,
            self.dataset,
            58,
            {"description": self.new_description},
            f"description set to {self.new_description}",
        )

    def test_eventlog_does_not_runs_when_dataset_description_has_not_changed(
        self, mock_log_permission_change
    ):
        eventlog_count = EventLog.objects.count()
        response = self.client.post(
            reverse("datasets:edit_dataset", args=(self.dataset.id,)),
            data={
                "name": "test",
                "short_description": "test",
                "government_security_classification": 2,
                "description": self.description,
            },
        )
        assert response.status_code == 302
        assert (
            EventLog.objects.filter(event_type=EventLog.TYPE_CHANGED_DATASET_DESCRIPTION).count()
            == eventlog_count
        )

    def test_eventlog_runs_when_vis_description_changed(self, mock_log_permission_change):
        response = self.client.post(
            reverse("datasets:edit_visualisation_catalogue_item", args=(self.visualisation.id,)),
            data={
                "name": self.dataset.name,
                "short_description": "test",
                "description": self.new_description,
            },
        )
        assert response.status_code == 302
        mock_log_permission_change.assert_called_with(
            self.user,
            self.visualisation,
            58,
            {"description": self.new_description},
            f"description set to {self.new_description}",
        )

    def test_eventlog_does_not_runs_when_vis_description_has_not_changed(
        self, mock_log_permission_change
    ):
        eventlog_count = EventLog.objects.count()
        response = self.client.post(
            reverse("datasets:edit_visualisation_catalogue_item", args=(self.visualisation.id,)),
            data={"name": "test", "short_description": "test", "description": self.description},
        )
        assert response.status_code == 302
        assert (
            EventLog.objects.filter(event_type=EventLog.TYPE_CHANGED_DATASET_DESCRIPTION).count()
            == eventlog_count
        )


@pytest.mark.parametrize(
    "permissions, result_dataset_names",
    (
        (["manage_unpublished_master_datasets"], {"Master dataset"}),
        (["manage_unpublished_datacut_datasets"], {"Datacut dataset"}),
        (["manage_unpublished_reference_datasets"], {"Reference dataset"}),
        (["manage_unpublished_visualisations"], {"Visualisation"}),
        (
            [
                "manage_unpublished_master_datasets",
                "manage_unpublished_datacut_datasets",
            ],
            {"Master dataset", "Datacut dataset"},
        ),
        (
            [
                "manage_unpublished_master_datasets",
                "manage_unpublished_reference_datasets",
            ],
            {"Master dataset", "Reference dataset"},
        ),
        (
            [
                "manage_unpublished_datacut_datasets",
                "manage_unpublished_reference_datasets",
            ],
            {"Datacut dataset", "Reference dataset"},
        ),
        (
            [
                "manage_unpublished_master_datasets",
                "manage_unpublished_datacut_datasets",
                "manage_unpublished_reference_datasets",
            ],
            {"Master dataset", "Datacut dataset", "Reference dataset"},
        ),
        (
            ["manage_unpublished_master_datasets", "manage_unpublished_visualisations"],
            {"Master dataset", "Visualisation"},
        ),
        (
            [
                "manage_unpublished_master_datasets",
                "manage_unpublished_reference_datasets",
                "manage_unpublished_visualisations",
            ],
            {"Master dataset", "Reference dataset", "Visualisation"},
        ),
    ),
)
@pytest.mark.django_db
def test_find_datasets_includes_unpublished_results_based_on_permissions(
    permissions, result_dataset_names
):
    email = "test.user@example.com"
    user = get_user_model().objects.create(is_staff=True, email=email, username=email)
    perms = Permission.objects.filter(codename__in=permissions).all()
    user.user_permissions.add(*perms)
    user.save()

    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=False, type=DataSetType.MASTER, name="Master dataset"
    )
    factories.DataSetFactory.create(
        published=False, type=DataSetType.DATACUT, name="Datacut dataset"
    )
    factories.ReferenceDatasetFactory.create(published=False, name="Reference dataset")

    factories.VisualisationCatalogueItemFactory.create(published=False, name="Visualisation")

    response = client.get(reverse("datasets:find_datasets"), {"admin_filters": "unpublished"})

    assert response.status_code == 200
    assert {dataset["name"] for dataset in response.context["datasets"]} == result_dataset_names


class DatasetsCommon:
    def _get_database(self):
        return factories.DatabaseFactory.create(memorable_name="my_database")

    def _create_master(
        self,
        schema="public",
        table="test_dataset",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    ):
        master = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="A master",
            user_access_type=user_access_type,
        )
        factories.SourceTableFactory.create(
            dataset=master,
            schema=schema,
            table=table,
            database=self._get_database(),
        )

        return master

    def _create_external_link(self):
        pass

    def _create_related_data_cuts(
        self,
        schema="public",
        table="test_dataset",
        num=1,
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    ):
        datacuts = []

        for i in range(num):
            datacut = factories.DataSetFactory.create(
                published=True,
                type=DataSetType.DATACUT,
                name=f"Datacut {i}",
                user_access_type=user_access_type,
            )
            query = factories.CustomDatasetQueryFactory.create(
                dataset=datacut,
                database=self._get_database(),
                query=f'SELECT * FROM "{schema}"."{table}" order by id desc limit 10',
            )
            factories.CustomDatasetQueryTableFactory.create(
                query=query, schema=schema, table=table
            )
            datacuts.append(datacut)

        return datacuts

    def _create_related_visualisations(
        self,
        master,
        num=1,
    ):
        visualisations = []
        for _ in range(num):
            visualisation = factories.VisualisationCatalogueItemFactory.create()
            visualisation.datasets.add(master)
            visualisations.append(visualisation)

        return visualisations


class TestMasterDatasetDetailView(DatasetsCommon):
    @pytest.mark.django_db
    def test_master_dataset_detail_page_shows_related_data_cuts(self, staff_client, metadata_db):
        master = self._create_master()
        self._create_related_data_cuts(num=2)

        url = reverse("datasets:dataset_detail", args=(master.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["related_data"]) == 2

    def test_master_dataset_detail_page_shows_related_visualisations(
        self, staff_client, metadata_db
    ):
        master = self._create_master()
        self._create_related_visualisations(master, num=2)

        url = reverse("datasets:dataset_detail", args=(master.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["related_visualisations"]) == 2

    @pytest.mark.django_db
    def test_master_dataset_detail_page_shows_link_to_related_data_cuts_if_more_than_four(
        self, staff_client, metadata_db
    ):
        master = self._create_master()
        self._create_related_data_cuts(num=5)

        url = reverse("datasets:dataset_detail", args=(master.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["related_data"]) == 5
        assert "Show all related data" in response.content.decode(response.charset)

    def test_master_dataset_detail_page_shows_link_to_related_visualisations_if_more_than_four(
        self, staff_client, metadata_db
    ):
        master = self._create_master()
        self._create_related_visualisations(master, num=5)

        url = reverse("datasets:dataset_detail", args=(master.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["related_visualisations"]) == 5
        assert "Show all related dashboards" in response.content.decode(response.charset)

    @pytest.mark.django_db
    def test_master_dataset_subscription(self):
        master = factories.DataSetFactory.create(
            type=DataSetType.MASTER,
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        )
        user = get_user_model().objects.create(email="test@example.com", is_superuser=False)
        factories.DataSetUserPermissionFactory.create(user=user, dataset=master)

        client = Client(**get_http_sso_data(user))
        response = client.get(master.get_absolute_url())
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is False
        assert response.context["subscription"]["details"] is None

        subscription = master.subscriptions.create(user=user, notify_on_schema_change=True)

        response = client.get(master.get_absolute_url())
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is True
        assert response.context["subscription"]["details"] == subscription


class TestDatacutDetailView(DatasetsCommon):
    @pytest.mark.django_db
    def test_datacut_dataset_subscription(self):
        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT,
            name="A datacut",
            user_access_type="REQUIRES_AUTHORIZATION",
        )
        user = get_user_model().objects.create(email="test@example.com", is_superuser=False)
        factories.DataSetUserPermissionFactory.create(user=user, dataset=datacut)

        client = Client(**get_http_sso_data(user))
        url = reverse("datasets:dataset_detail", args=(datacut.id,))
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is False
        assert response.context["subscription"]["details"] is None

        subscription = datacut.subscriptions.create(user=user, notify_on_schema_change=True)

        assert datacut.subscriptions.filter(user=user).count() == 1

        response = client.get(url)
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is True
        assert response.context["subscription"]["details"] == subscription


class TestReferenceDatasetDetailView(DatasetsCommon):
    def _get_ref_dataset(self, table_name: str):
        return factories.ReferenceDatasetFactory.create(
            published=True,
            table_name=table_name,
            name="A search reference dataset",
            external_database=factories.DatabaseFactory.create(memorable_name="my_database"),
        )

    @mock.patch("dataworkspace.apps.datasets.models.ReferenceDataset.sync_to_external_database")
    def test_reference_dataset_show_link_to_license(self, mock_sync, staff_client):
        rds = self._get_ref_dataset("ref_test_license_url")

        rds.licence = "Open Gov"
        rds.licence_url = "http://www.example.com/"
        rds.save()

        response = staff_client.get(rds.get_absolute_url())
        assert response.status_code == 200

        response_body = response.content.decode(response.charset)
        doc = html.fromstring(response_body)

        match = doc.xpath(
            '//dt[@class="govuk-summary-list__key" and text()="Licence"]/../dd/a/@href'
        )

        assert match
        assert match[0] == rds.licence_url

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    def test_reference_dataset_shows_show_all_columns_link(self, request_client, published):
        group = factories.DataGroupingFactory.create()
        linked_rds = factories.ReferenceDatasetFactory.create(
            group=group, table_name="test_get_ref_data_linked"
        )
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name="id", data_type=2, is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name="name", data_type=1
        )
        rds = factories.ReferenceDatasetFactory.create(
            published=published, group=group, table_name="test_get_ref_data"
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="linked: id",
            relationship_name="rel_1",
            data_type=8,
            linked_reference_dataset_field=linked_field1,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="linked: name",
            relationship_name="rel_1",
            data_type=8,
            linked_reference_dataset_field=linked_field2,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="auto uuid",
            column_name="auto_uuid",
            data_type=9,
            sort_order=4,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name1", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name2", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name3", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name4", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name5", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name6", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name7", data_type=1
        )
        response = request_client.get(rds.get_absolute_url())

        assert response.status_code == 200
        assert "View all columns" not in response.content.decode(response.charset)

    @pytest.mark.django_db
    def test_reference_dataset_subscription(self):
        rds = factories.ReferenceDatasetFactory.create(
            published=True,
        )
        user = get_user_model().objects.create(email="test@example.com", is_superuser=False)

        client = Client(**get_http_sso_data(user))
        url = reverse("datasets:dataset_detail", args=(rds.uuid,))
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is False
        assert response.context["subscription"]["details"] is None

        subscription = rds.subscriptions.create(user=user, notify_on_schema_change=True)

        assert rds.subscriptions.filter(user=user).count() == 1

        response = client.get(url)
        assert response.status_code == 200
        assert response.context["subscription"]["current_user_is_subscribed"] is True
        assert response.context["subscription"]["details"] == subscription


class TestRequestAccess(DatasetsCommon):
    @pytest.mark.django_db
    def test_unauthorised_dataset(self, staff_client, metadata_db):
        master = self._create_master(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)

        url = reverse("datasets:dataset_detail", args=(master.id,))
        response = staff_client.get(url)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_when_user_has_data_access_only(self, access_type, db, staff_user, metadata_db):
        master = self._create_master(user_access_type=access_type)
        url = reverse("datasets:dataset_detail", args=(master.id,))
        client = get_client(get_user_data(staff_user))
        response = client.get(url)

        assert response.status_code == 200

    def test_when_user_has_tools_access_only(self, db, staff_user, metadata_db):
        master = self._create_master(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        url = reverse("datasets:dataset_detail", args=(master.id,))

        # grant tools permissions
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        staff_user.user_permissions.add(permission)
        client = get_client(get_user_data(staff_user))

        response = client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_unauthorised_datacut(self, staff_client, metadata_db):
        self._create_master(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        datacuts = self._create_related_data_cuts(num=1)

        datacut = datacuts[0]
        datacut.user_access_type = UserAccessType.REQUIRES_AUTHORIZATION
        datacut.save()

        url = reverse("datasets:dataset_detail", args=(datacut.id,))
        response = staff_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_unauthorised_visualisation(self, staff_client, metadata_db):
        ds = factories.VisualisationCatalogueItemFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )

        url = reverse("datasets:dataset_detail", args=(ds.id,))
        response = staff_client.get(url)
        assert response.status_code == 200


def get_govuk_summary_list_value(doc, key_text, selector):
    # xpath hint ... the first dd child of the parent of the dt element containing key_text
    match = doc.xpath(f'//dt[@class="{selector}" and text()="{key_text}"]/../dd/text()')

    if match:
        return match[0]

    # Don't want to return an empty string as this could give false positives
    return "<empty>"


class TestVisualisationsDetailView:
    def test_get_published_authenticated_visualisation(self, client, user):
        vis = VisualisationCatalogueItemFactory()

        vis.enquiries_contact = user
        vis.short_description = faker.Faker().sentence()
        vis.save()

        response = client.get(vis.get_absolute_url())

        response_content = response.content.decode(response.charset)
        doc = html.fromstring(response_content)

        assert response.status_code == 200
        assert vis.name in response_content

        assert (
            get_govuk_summary_list_value(doc, "Update frequency", "govuk-summary-list__key")
            == "N/A"
        )
        assert (
            get_govuk_summary_list_value(doc, "Summary", "govuk-summary-list__key__stacked")
            == vis.short_description
        )

    @pytest.mark.parametrize("has_access", (True, False))
    @pytest.mark.django_db
    def test_unauthorised_visualisation(self, has_access):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )

        if has_access:
            VisualisationUserPermissionFactory.create(visualisation=vis, user=user)

        client = Client(**get_http_sso_data(user))
        response = client.get(vis.get_absolute_url())

        assert response.status_code == 200
        assert vis.name in response.content.decode(response.charset)

    @pytest.mark.django_db
    def test_shows_links_to_visualisations(self):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            visualisation_template__host_basename="visualisation",
        )

        VisualisationUserPermissionFactory.create(visualisation=vis, user=user)
        vis.has_access = True
        vis.save()

        link1 = VisualisationLinkFactory.create(
            visualisation_type="QUICKSIGHT",
            visualisation_catalogue_item=vis,
            name="Visualisation quicksight",
            identifier="5d75e131-20f4-48f8-b0eb-f4ebf36434f4",
        )

        client = Client(**get_http_sso_data(user))
        response = client.get(vis.get_absolute_url())
        body = response.content.decode(response.charset)

        assert response.status_code == 200
        assert "//visualisation.dataworkspace.test:8000/" in body
        assert f"/visualisations/link/{link1.id}" in body


class TestVisualisationLinkView:
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_quicksight_link(self, access_type, mocker):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(user_access_type=access_type)
        link = VisualisationLinkFactory.create(
            visualisation_type="QUICKSIGHT",
            identifier="5d75e131-20f4-48f8-b0eb-f4ebf36434f4",
            visualisation_catalogue_item=vis,
        )

        quicksight = mocker.patch(
            "dataworkspace.apps.applications.views.get_quicksight_dashboard_name_url"
        )
        quicksight.return_value = (
            "my-dashboard",
            "https://my.dashboard.quicksight.amazonaws.com",
        )
        eventlog_count = EventLog.objects.count()

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())

        assert response.status_code == 200
        assert "https://my.dashboard.quicksight.amazonaws.com" in response.content.decode(
            response.charset
        )
        assert (
            "frame-src https://eu-west-2.quicksight.aws.amazon.com"
            in response["content-security-policy"]
        )
        assert (
            "frame-ancestors dataworkspace.test:8000 https://authorized-embedder.com"
            in response["content-security-policy"]
        )
        assert EventLog.objects.count() == eventlog_count + 1
        assert (
            list(EventLog.objects.all())[-1].event_type
            == EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION
        )

    @pytest.mark.django_db
    def test_user_needs_access_via_catalogue_item(self, mocker):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        link = VisualisationLinkFactory.create(
            visualisation_type="QUICKSIGHT",
            identifier=str(uuid4()),
            visualisation_catalogue_item=vis,
        )
        quicksight = mocker.patch(
            "dataworkspace.apps.applications.views.get_quicksight_dashboard_name_url"
        )
        quicksight.return_value = (
            "my-dashboard",
            "https://my.dashboard.quicksight.amazonaws.com",
        )

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())
        assert response.status_code == 302

        VisualisationUserPermissionFactory.create(visualisation=vis, user=user)

        response = client.get(link.get_absolute_url())
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_invalid_link_404s(self):
        user = UserFactory.create()

        client = Client(**get_http_sso_data(user))
        response = client.get(
            reverse(
                "visualisations:link",
                kwargs={"link_id": "2af5890a-bbcc-4e7d-8b2d-2a63139b3e4f"},
            )
        )
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_access_denied_redirect(self):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        link = VisualisationLinkFactory.create(
            visualisation_type="QUICKSIGHT",
            identifier=str(uuid4()),
            visualisation_catalogue_item=vis,
        )

        with mock.patch("dataworkspace.apps.applications.views.get_quicksight_dashboard_name_url"):
            client = Client(**get_http_sso_data(user))
            response = client.get(link.get_absolute_url())

            assert response.status_code == 302
            assert response.headers["Location"] == reverse(
                "datasets:dataset_detail", args=(link.visualisation_catalogue_item_id,)
            )


def test_find_datasets_search_by_source_name(client):
    source = factories.SourceTagFactory(name="source1")
    source_2 = factories.SourceTagFactory(name="source2")
    ds1 = factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    ds1.tags.set([source, source_2])
    ds1.save()

    ds2 = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    ds2.tags.set([factories.SourceTagFactory(name="source3")])
    ds2.save()

    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    rds.tags.set([source])
    rds.save()

    response = client.get(reverse("datasets:find_datasets"), {"q": "source1"})

    assert response.status_code == 200
    expected_results = [
        expected_search_result(
            ds1,
            search_rank=0.12158542,
            source_tag_ids=MatchUnorderedMembers([source.id, source_2.id]),
            has_access=False,
        ),
        expected_search_result(
            rds,
            search_rank=0.12158542,
            data_type=DataSetType.REFERENCE,
        ),
    ]

    results = list(response.context["datasets"])
    assert len(results) == 2

    for expected in expected_results:
        assert expected in results


def test_find_datasets_search_by_topic_name(client):
    topic = factories.TopicTagFactory.create(name="topic1")
    topic_2 = factories.TopicTagFactory.create(name="topic2")
    ds1 = factories.DataSetFactory.create(published=True, type=1, name="A dataset")
    ds1.tags.set([topic, topic_2])
    ds1.save()

    ds2 = factories.DataSetFactory.create(published=True, type=2, name="A new dataset")
    ds2.tags.set([factories.TopicTagFactory.create(name="topic3")])
    ds2.save()

    rds = factories.ReferenceDatasetFactory.create(published=True, name="A new reference dataset")
    rds.tags.set([topic])
    rds.save()

    response = client.get(reverse("datasets:find_datasets"), {"q": "topic1"})

    assert response.status_code == 200
    expected_results = [
        expected_search_result(
            ds1,
            search_rank=0.12158542,
            topic_tag_ids=MatchUnorderedMembers([topic.id, topic_2.id]),
            has_access=False,
        ),
        expected_search_result(
            rds,
            search_rank=0.12158542,
            topic_tag_ids=[topic.id],
        ),
    ]

    results = list(response.context["datasets"])
    assert len(results) == 2

    for expected in expected_results:
        assert expected in results


def test_find_datasets_name_weighting(client):
    ds1 = factories.DataSetFactory.create(published=True, type=1, name="A dataset with a keyword")
    ds2 = factories.DataSetFactory.create(
        published=True,
        type=2,
        name="A dataset",
        short_description="Keyword appears in short description",
    )
    factories.DataSetFactory.create(published=True, type=1, name="Does not appear in search")
    ds4 = factories.DataSetFactory.create(
        published=True,
        type=2,
        name="Another dataset but the keyword appears twice, keyword.",
    )

    response = client.get(reverse("datasets:find_datasets"), {"q": "keyword"})

    assert response.status_code == 200
    expected_results = [
        expected_search_result(
            ds4,
            has_access=False,
            search_rank=0.75990885,
        ),
        expected_search_result(ds1, has_access=False, search_rank=0.6079271),
        expected_search_result(ds2, has_access=False, search_rank=0.24317084),
    ]

    results = list(response.context["datasets"])
    assert len(results) == 3

    for expected in expected_results:
        assert expected in results


def test_find_datasets_matches_both_source_and_name(client):
    source_1 = factories.SourceTagFactory(name="source1")
    source_2 = factories.SourceTagFactory(name="source2")

    ds1 = factories.DataSetFactory.create(published=True, type=1, name="A dataset from source1")
    ds1.tags.set([source_1, source_2])

    response = client.get(reverse("datasets:find_datasets"), {"q": "source1"})

    assert response.status_code == 200
    assert len(list(response.context["datasets"])) == 1
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            source_tag_ids=MatchUnorderedMembers([source_1.id, source_2.id]),
            has_access=False,
        )
    ]


def test_find_datasets_matches_both_full_description(client):
    ds1 = factories.DataSetFactory.create(
        published=True,
        type=1,
        name="dataset1",
        short_description="short datasset1",
        description="this is long description",
    )

    factories.DataSetFactory.create(
        published=True,
        type=1,
        name="dataset2",
        short_description="short datasset2",
        description="nothing",
    )

    response = client.get(reverse("datasets:find_datasets"), {"q": "description"})

    assert response.status_code == 200
    assert len(list(response.context["datasets"])) == 1
    assert list(response.context["datasets"]) == [
        expected_search_result(
            ds1,
            has_access=False,
        )
    ]


class TestCustomQueryRelatedDataView:
    def _get_dsn(self):
        return database_dsn(settings.DATABASES_DATA["my_database"])

    def _get_database(self):
        return factories.DatabaseFactory(memorable_name="my_database")

    def _setup_datacut_with_masters(self, access_type, sql, master_count=1, published=True):
        masters = []
        for _ in range(master_count):
            master = factories.DataSetFactory.create(
                published=published,
                type=DataSetType.MASTER,
                name="A master 1",
                user_access_type=access_type,
            )
            factories.SourceTableFactory.create(
                dataset=master,
                schema="public",
                table="test_dataset",
                database=self._get_database(),
            )
            masters.append(master)
        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT,
            name="A datacut",
            user_access_type=access_type,
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query=sql,
        )
        factories.CustomDatasetQueryTableFactory(
            query=query, schema="public", table="test_dataset"
        )
        return datacut, masters

    def _setup_new_table(self):
        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS custom_query_test (
                    id INT,
                    name VARCHAR(255),
                    date DATE
                );
                TRUNCATE TABLE custom_query_test;
                INSERT INTO custom_query_test VALUES(1, 'the first record', NULL);
                INSERT INTO custom_query_test VALUES(2, 'the second record', '2019-01-01');
                INSERT INTO custom_query_test VALUES(3, 'the last record', NULL);
                """
            )

    @pytest.mark.parametrize(
        "request_client, master_count, status",
        (
            ("sme_client", 1, 200),
            ("staff_client", 1, 200),
            ("sme_client", 3, 200),
            ("staff_client", 3, 200),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_related_dataset_dataset(self, access_type, request_client, master_count, status):
        datacut, masters = self._setup_datacut_with_masters(
            access_type,
            "SELECT * FROM test_dataset order by id desc limit 10",
            master_count=master_count,
            published=True,
        )
        url = reverse("datasets:dataset_detail", args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_data"]) == master_count
        for master in masters:
            related_master = [
                item for item in response.context["related_data"] if item.id == master.id
            ][0]
            assert related_master.id == master.id
            assert related_master.name == master.name

    @pytest.mark.parametrize(
        "request_client, master_count, status",
        (
            ("sme_client", 1, 200),
            ("staff_client", 1, 200),
            ("sme_client", 3, 200),
            ("staff_client", 3, 200),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_related_dataset_hide_unpublished_master(
        self, access_type, request_client, master_count, status
    ):
        published_master = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="Published master",
            user_access_type=access_type,
        )
        factories.SourceTableFactory.create(
            dataset=published_master,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )
        unpublished_master = factories.DataSetFactory.create(
            published=False,
            type=DataSetType.MASTER,
            name="Unpublished master",
            user_access_type=access_type,
        )
        factories.SourceTableFactory.create(
            dataset=unpublished_master,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )

        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT,
            name="A datacut",
            user_access_type=access_type,
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query="SELECT * FROM test_dataset order by id desc limit 10",
        )
        factories.CustomDatasetQueryTableFactory(
            query=query, schema="public", table="test_dataset"
        )

        url = reverse("datasets:dataset_detail", args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_data"]) == 1

    @pytest.mark.parametrize(
        "request_client, status",
        (("sme_client", 200), ("staff_client", 200)),
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_related_dataset_does_not_duplicate_masters(self, access_type, request_client, status):
        self._setup_new_table()
        master1 = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="A master 1",
            user_access_type=access_type,
        )
        factories.SourceTableFactory.create(
            dataset=master1,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )
        factories.SourceTableFactory.create(
            dataset=master1,
            schema="public",
            table="custom_query_test",
            database=self._get_database(),
        )

        master2 = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="A master 1",
            user_access_type=access_type,
        )
        factories.SourceTableFactory.create(
            dataset=master2,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )

        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT,
            name="A datacut",
            user_access_type=access_type,
        )
        query1 = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query="SELECT * FROM test_dataset order by id desc limit 10",
        )
        factories.CustomDatasetQueryTableFactory(
            query=query1, schema="public", table="test_dataset"
        )
        query2 = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query="SELECT * FROM custom_query_test order by id desc limit 10",
        )
        factories.CustomDatasetQueryTableFactory(
            query=query2, schema="public", table="custom_query_test"
        )

        url = reverse("datasets:dataset_detail", args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_data"]) == 2


class TestColumnDetailsView:
    @pytest.mark.parametrize(
        "dataset_type,source_factory",
        (
            (DataSetType.MASTER, factories.SourceTableFactory),
            (DataSetType.DATACUT, factories.CustomDatasetQueryFactory),
        ),
    )
    @mock.patch("dataworkspace.apps.datasets.views.datasets_db.get_columns")
    @pytest.mark.django_db
    def test_page_shows_all_columns_for_dataset(
        self, get_columns_mock, dataset_type, source_factory, user, client
    ):
        ds = factories.DataSetFactory.create(type=dataset_type, published=True)
        factories.DataSetUserPermissionFactory.create(user=user, dataset=ds)
        source = source_factory.create(
            dataset=ds,
            database=factories.DatabaseFactory(memorable_name="my_database"),
        )
        get_columns_mock.return_value = [(f"column_{i}", "integer") for i in range(100)]
        response = client.get(source.get_column_details_url())
        response_body = response.content.decode(response.charset)
        assert response.status_code == 200
        for i in range(100):
            assert f"<strong>column_{i}</strong> (integer)" in response_body

    @pytest.mark.parametrize(
        "dataset_type,source_factory,source_type,url_param",
        (
            (
                DataSetType.MASTER,
                factories.SourceTableFactory,
                "source_table",
                "table_uuid",
            ),
            (
                DataSetType.DATACUT,
                factories.CustomDatasetQueryFactory,
                "custom_query",
                "query_id",
            ),
        ),
    )
    @mock.patch("dataworkspace.apps.datasets.views.datasets_db.get_columns")
    @pytest.mark.django_db
    def test_404_if_wrong_dataset_for_source_table_in_url(
        self,
        get_columns_mock,
        dataset_type,
        source_factory,
        source_type,
        url_param,
        client,
    ):
        ds1 = factories.DataSetFactory.create(type=dataset_type, published=True)
        ds2 = factories.DataSetFactory.create(type=dataset_type, published=True)
        source = source_factory.create(
            dataset=ds2,
            database=factories.DatabaseFactory(memorable_name="my_database"),
        )
        response = client.get(
            reverse(
                f"datasets:{source_type}_column_details",
                kwargs={"dataset_uuid": ds1.id, url_param: source.id},
            )
        )
        assert response.status_code == 404


class TestRelatedDataView:
    def _get_database(self):
        return factories.DatabaseFactory.create(memorable_name="my_database")

    def _create_master(self):
        master = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="A master",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )
        factories.SourceTableFactory.create(
            dataset=master,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )

        return master

    def _create_related_data_cuts(self, master, num=1):
        datacuts = []

        for i in range(num):
            datacut = factories.DataSetFactory.create(
                published=True,
                type=DataSetType.DATACUT,
                name=f"Datacut {i}",
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            )
            query = factories.CustomDatasetQueryFactory.create(
                dataset=datacut,
                database=self._get_database(),
                query="SELECT * FROM test_dataset order by id desc limit 10",
            )
            factories.CustomDatasetQueryTableFactory.create(
                query=query, schema="public", table="test_dataset"
            )
            datacuts.append(datacut)

        return datacuts

    def test_view_shows_all_related_data_cuts(self, staff_client):
        master = self._create_master()
        datacuts = self._create_related_data_cuts(master, num=5)

        url = reverse("datasets:related_data", args=(master.id,))
        response = staff_client.get(url)
        body = response.content.decode(response.charset)
        assert response.status_code == 200
        assert len(response.context["related_data"]) == 5
        assert all(datacut.name in body for datacut in datacuts)

    class TestRelatedVisualisationsView(DatasetsCommon):
        def test_view_shows_all_related_visualisations(self, staff_client):
            master = self._create_master()
            visualisations = self._create_related_visualisations(master, num=5)

            url = reverse("datasets:related_visualisations", args=(master.id,))
            response = staff_client.get(url)
            body = response.content.decode(response.charset)
            assert response.status_code == 200
            assert len(response.context["related_visualisations"]) == 5
            assert all(visualisation.name in body for visualisation in visualisations)


class TestDatasetUsageHistory:
    @pytest.fixture
    def dataset(self):
        return factories.DataSetFactory.create(
            type=DataSetType.DATACUT,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )

    @pytest.fixture
    def visualisation(self):
        return factories.VisualisationCatalogueItemFactory(
            visualisation_template__gitlab_project_id=1,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "url_name, fixture_name, event_factory, event_type",
        (
            (
                "usage_history",
                "dataset",
                factories.DatasetLinkDownloadEventFactory,
                "Downloaded",
            ),
            (
                "visualisation_usage_history",
                "visualisation",
                factories.VisualisationViewedEventFactory,
                "Viewed",
            ),
        ),
    )
    def test_one_event_by_one_user_on_the_same_day(
        self, url_name, fixture_name, event_factory, event_type, staff_client, request
    ):
        catalogue_item = request.getfixturevalue(fixture_name)
        user = factories.UserFactory(email="test-user@example.com")
        with freeze_time("2021-01-01"):
            event_factory(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event"}},
            )

        url = reverse(f"datasets:{url_name}", args=(catalogue_item.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 1
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "url_name, fixture_name, event_factory1, event_factory2, event_type",
        (
            (
                "usage_history",
                "dataset",
                factories.DatasetLinkDownloadEventFactory,
                factories.DatasetQueryDownloadEventFactory,
                "Downloaded",
            ),
            (
                "visualisation_usage_history",
                "visualisation",
                factories.VisualisationViewedEventFactory,
                factories.SupersetVisualisationViewedEventFactory,
                "Viewed",
            ),
        ),
    )
    def test_multiple_events_by_one_user_on_the_same_day(
        self,
        url_name,
        fixture_name,
        event_factory1,
        event_factory2,
        event_type,
        staff_client,
        request,
    ):
        catalogue_item = request.getfixturevalue(fixture_name)
        user = factories.UserFactory(email="test-user@example.com")
        with freeze_time("2021-01-01"):
            event_factory1(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 1"}},
            )
            event_factory2.create_batch(
                2,
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 2"}},
            )

        url = reverse(f"datasets:{url_name}", args=(catalogue_item.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 2
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 1",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 2",
            "count": 2,
            "event": event_type,
        } in response.context["rows"]

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "url_name, fixture_name, event_factory1, event_factory2, event_type",
        (
            (
                "usage_history",
                "dataset",
                factories.DatasetLinkDownloadEventFactory,
                factories.DatasetQueryDownloadEventFactory,
                "Downloaded",
            ),
            (
                "visualisation_usage_history",
                "visualisation",
                factories.VisualisationViewedEventFactory,
                factories.SupersetVisualisationViewedEventFactory,
                "Viewed",
            ),
        ),
    )
    def test_multiple_events_by_multiple_users_on_the_same_day(
        self,
        url_name,
        fixture_name,
        event_factory1,
        event_factory2,
        event_type,
        staff_client,
        request,
    ):
        catalogue_item = request.getfixturevalue(fixture_name)
        user = factories.UserFactory(email="test-user@example.com")
        user_2 = factories.UserFactory(email="test-user-2@example.com")
        with freeze_time("2021-01-01"):
            event_factory1(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 1"}},
            )
            event_factory2.create_batch(
                3,
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 2"}},
            )
            event_factory2(
                content_object=catalogue_item,
                user=user_2,
                extra={"fields": {"name": "Test Event 2"}},
            )

        url = reverse(f"datasets:{url_name}", args=(catalogue_item.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 3

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 1",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 2",
            "count": 3,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "Test Event 2",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "url_name, fixture_name, event_factory1, event_factory2, event_type",
        (
            (
                "usage_history",
                "dataset",
                factories.DatasetLinkDownloadEventFactory,
                factories.DatasetQueryDownloadEventFactory,
                "Downloaded",
            ),
            (
                "visualisation_usage_history",
                "visualisation",
                factories.VisualisationViewedEventFactory,
                factories.SupersetVisualisationViewedEventFactory,
                "Viewed",
            ),
        ),
    )
    def test_multiple_events_by_multiple_users_on_different_days(
        self,
        url_name,
        fixture_name,
        event_factory1,
        event_factory2,
        event_type,
        staff_client,
        request,
    ):
        catalogue_item = request.getfixturevalue(fixture_name)
        user = factories.UserFactory(email="test-user@example.com")
        user_2 = factories.UserFactory(email="test-user-2@example.com")
        with freeze_time("2021-01-01"):
            event_factory1(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 1"}},
            )
            event_factory2.create_batch(
                3,
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 2"}},
            )
            event_factory2(
                content_object=catalogue_item,
                user=user_2,
                extra={"fields": {"name": "Test Event 2"}},
            )

        with freeze_time("2021-01-02"):
            event_factory1(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 1"}},
            )
            event_factory1.create_batch(
                4,
                content_object=catalogue_item,
                user=user_2,
                extra={"fields": {"name": "Test Event 1"}},
            )

            event_factory2(
                content_object=catalogue_item,
                user=user,
                extra={"fields": {"name": "Test Event 2"}},
            )

        url = reverse(f"datasets:{url_name}", args=(catalogue_item.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 6

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 1",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 2",
            "count": 3,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "Test Event 2",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 1",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "Test Event 1",
            "count": 4,
            "event": event_type,
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "Test Event 2",
            "count": 1,
            "event": event_type,
        } in response.context["rows"]


class TestMasterDatasetUsageHistory:
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_one_event_by_one_user_on_the_same_day(self, access_type, staff_client):
        dataset = factories.DataSetFactory.create(
            type=DataSetType.MASTER,
            user_access_type=access_type,
        )
        table = factories.SourceTableFactory.create(dataset=dataset, table="test_table")
        user = factories.UserFactory(email="test-user@example.com")

        factories.ToolQueryAuditLogTableFactory(
            table=table.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        url = reverse("datasets:usage_history", args=(dataset.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 1
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_multiple_events_by_one_user_on_the_same_day(self, access_type, staff_client):
        dataset = factories.DataSetFactory.create(
            type=DataSetType.MASTER,
            user_access_type=access_type,
        )
        table = factories.SourceTableFactory.create(dataset=dataset, table="test_table")
        table_2 = factories.SourceTableFactory.create(dataset=dataset, table="test_table_2")
        user = factories.UserFactory(email="test-user@example.com")

        factories.ToolQueryAuditLogTableFactory(
            table=table.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        for _ in range(2):
            factories.ToolQueryAuditLogTableFactory(
                table=table_2.table,
                audit_log__user=user,
                audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            )

        url = reverse("datasets:usage_history", args=(dataset.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 2
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table_2",
            "count": 2,
            "event": "Queried",
        } in response.context["rows"]

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_multiple_events_by_multiple_users_on_the_same_day(self, access_type, staff_client):
        dataset = factories.DataSetFactory.create(
            type=DataSetType.MASTER,
            user_access_type=access_type,
        )
        table = factories.SourceTableFactory.create(dataset=dataset, table="test_table")
        table_2 = factories.SourceTableFactory.create(dataset=dataset, table="test_table_2")
        user = factories.UserFactory(email="test-user@example.com")
        user_2 = factories.UserFactory(email="test-user-2@example.com")

        factories.ToolQueryAuditLogTableFactory(
            table=table.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        for _ in range(3):
            factories.ToolQueryAuditLogTableFactory(
                table=table_2.table,
                audit_log__user=user,
                audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            )

        factories.ToolQueryAuditLogTableFactory(
            table=table_2.table,
            audit_log__user=user_2,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        url = reverse("datasets:usage_history", args=(dataset.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 3
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table_2",
            "count": 3,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "test_table_2",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_multiple_events_by_multiple_users_on_different_days(self, access_type, staff_client):
        dataset = factories.DataSetFactory.create(
            type=DataSetType.MASTER,
            user_access_type=access_type,
        )
        table = factories.SourceTableFactory.create(dataset=dataset, table="test_table")
        table_2 = factories.SourceTableFactory.create(dataset=dataset, table="test_table_2")
        user = factories.UserFactory(email="test-user@example.com")
        user_2 = factories.UserFactory(email="test-user-2@example.com")

        factories.ToolQueryAuditLogTableFactory(
            table=table.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        for _ in range(3):
            factories.ToolQueryAuditLogTableFactory(
                table=table_2.table,
                audit_log__user=user,
                audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            )

        factories.ToolQueryAuditLogTableFactory(
            table=table_2.table,
            audit_log__user=user_2,
            audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        factories.ToolQueryAuditLogTableFactory(
            table=table.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 2, tzinfo=timezone.utc),
        )

        for _ in range(4):
            factories.ToolQueryAuditLogTableFactory(
                table=table.table,
                audit_log__user=user_2,
                audit_log__timestamp=datetime(2021, 1, 2, tzinfo=timezone.utc),
            )

        factories.ToolQueryAuditLogTableFactory(
            table=table_2.table,
            audit_log__user=user,
            audit_log__timestamp=datetime(2021, 1, 2, tzinfo=timezone.utc),
        )

        url = reverse("datasets:usage_history", args=(dataset.id,))
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.context["rows"]) == 6
        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table_2",
            "count": 3,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "test_table_2",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user-2@example.com",
            "object": "test_table",
            "count": 4,
            "event": "Queried",
        } in response.context["rows"]

        assert {
            "day": datetime(2021, 1, 2, tzinfo=timezone.utc),
            "email": "test-user@example.com",
            "object": "test_table_2",
            "count": 1,
            "event": "Queried",
        } in response.context["rows"]


class TestGridDataView:
    def _create_test_data(self):
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA["my_database"])
        ) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS source_data_test (
                    id UUID primary key,
                    name VARCHAR(255),
                    num NUMERIC,
                    date DATE,
                    an_array TEXT[]
                );
                TRUNCATE TABLE source_data_test;
                INSERT INTO source_data_test
                VALUES('896b4dde-f787-41be-a7bf-82be91805f24', 'the first record', 1, NULL, '{abc, def}');
                INSERT INTO source_data_test
                VALUES('488d06b6-032b-467a-b2c5-2820610b0ca6', 'the second record', 2, '2019-01-01', '{ghi, jkl}');
                INSERT INTO source_data_test
                VALUES('a41da88b-ffa3-4102-928c-b3937fa5b58f', 'the last record', NULL, '2020-01-01');
                """
            )

    @pytest.fixture
    def custom_query(self):
        self._create_test_data()
        dataset = factories.DataSetFactory(
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION, published=True
        )
        return factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name="my_database"),
            data_grid_enabled=True,
            query="SELECT * FROM source_data_test",
        )

    @pytest.fixture
    def source_table(self):
        self._create_test_data()
        dataset = factories.DataSetFactory(
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION, published=True
        )
        return factories.SourceTableFactory(
            dataset=dataset,
            schema="public",
            table="source_data_test",
            database=factories.DatabaseFactory(memorable_name="my_database"),
            data_grid_enabled=True,
        )

    @pytest.mark.django_db
    def test_download_reporting_disabled(self, client, custom_query):
        custom_query.data_grid_enabled = False
        custom_query.save()
        response = client.post(
            reverse(
                "datasets:custom_dataset_query_data",
                args=(custom_query.dataset.id, custom_query.id),
            )
            + "?download=1",
            data={"columns": ["id", "name", "num", "date"]},
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_source_table_download_disabled(self, client, source_table):
        response = client.post(
            reverse(
                "datasets:source_table_data",
                args=(source_table.dataset.id, source_table.id),
            )
            + "?download=1",
            data={"columns": ["id", "name", "num", "date"]},
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_no_count(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)),
            {
                "sort_direction": "ASC",
                "sort_field": "num",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": None},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                },
                {
                    "name": "the first record",
                    "num": "1",
                    "date": None,
                    "id": "896b4dde-f787-41be-a7bf-82be91805f24",
                    "an_array": ["abc", "def"],
                },
                {
                    "name": "the last record",
                    "num": None,
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "an_array": None,
                },
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_contains_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            {
                "filters": {
                    "name": {
                        "filter": "last",
                        "filterType": "text",
                        "type": "contains",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "name": "the last record",
                    "num": None,
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "an_array": None,
                }
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_not_contains_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "name": {
                        "filter": "last",
                        "filterType": "text",
                        "type": "notContains",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 2},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                },
                {
                    "date": None,
                    "id": "896b4dde-f787-41be-a7bf-82be91805f24",
                    "name": "the first record",
                    "num": "1",
                    "an_array": ["abc", "def"],
                },
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_equals_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "date": {
                        "dateFrom": "2019-01-01 00:00:00",
                        "dateTo": None,
                        "filterType": "date",
                        "type": "equals",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                }
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_not_equals_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "date": {
                        "dateFrom": "2019-01-01 00:00:00",
                        "dateTo": None,
                        "filterType": "date",
                        "type": "notEqual",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 2},
            "download_limit": None,
            "records": [
                {
                    "date": None,
                    "id": "896b4dde-f787-41be-a7bf-82be91805f24",
                    "name": "the first record",
                    "num": "1",
                    "an_array": ["abc", "def"],
                },
                {
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "name": "the last record",
                    "num": None,
                    "an_array": None,
                },
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_starts_with_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "name": {
                        "filter": "the last",
                        "filterType": "text",
                        "type": "startsWith",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "name": "the last record",
                    "num": None,
                    "an_array": None,
                }
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_ends_with_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "name": {
                        "filter": "first record",
                        "filterType": "text",
                        "type": "endsWith",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": None,
                    "id": "896b4dde-f787-41be-a7bf-82be91805f24",
                    "name": "the first record",
                    "num": "1",
                    "an_array": ["abc", "def"],
                }
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_range_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "date": {
                        "dateFrom": "2018-12-31 00:00:00",
                        "dateTo": "2019-01-03 00:00:00",
                        "filterType": "date",
                        "type": "inRange",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                }
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_less_than_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "date": {
                        "dateFrom": "2019-12-31 00:00:00",
                        "dateTo": None,
                        "filterType": "date",
                        "type": "lessThan",
                    }
                }
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                }
            ],
        }

    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_greater_than_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            data={
                "filters": {
                    "date": {
                        "dateFrom": "2019-12-31 00:00:00",
                        "dateTo": None,
                        "filterType": "date",
                        "type": "greaterThan",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "name": "the last record",
                    "num": None,
                    "an_array": None,
                }
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_array_contains_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            {
                "filters": {
                    "an_array": {
                        "filter": "ghi",
                        "filterType": "array",
                        "type": "contains",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                }
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_array_not_contains_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            {
                "filters": {
                    "an_array": {
                        "filter": "ghi",
                        "filterType": "array",
                        "type": "notContains",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 2},
            "download_limit": None,
            "records": [
                {
                    "date": None,
                    "id": "896b4dde-f787-41be-a7bf-82be91805f24",
                    "name": "the first record",
                    "num": "1",
                    "an_array": ["abc", "def"],
                },
                {
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "name": "the last record",
                    "num": None,
                    "an_array": None,
                },
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_array_equals_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            {
                "filters": {
                    "an_array": {
                        "filter": "ghi, jkl",
                        "filterType": "array",
                        "type": "equals",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 1},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                }
            ],
        }

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "fixture_name, url_name",
        (
            ("source_table", "source_table_data"),
            ("custom_query", "custom_dataset_query_data"),
        ),
    )
    def test_array_not_equals_filter(self, client, fixture_name, url_name, request):
        source = request.getfixturevalue(fixture_name)
        response = client.post(
            reverse(f"datasets:{url_name}", args=(source.dataset.id, source.id)) + "?count=1",
            {
                "filters": {
                    "an_array": {
                        "filter": "abc, def",
                        "filterType": "array",
                        "type": "notEqual",
                    }
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {
            "rowcount": {"count": 2},
            "download_limit": None,
            "records": [
                {
                    "date": "2019-01-01",
                    "id": "488d06b6-032b-467a-b2c5-2820610b0ca6",
                    "name": "the second record",
                    "num": "2",
                    "an_array": ["ghi", "jkl"],
                },
                {
                    "date": "2020-01-01",
                    "id": "a41da88b-ffa3-4102-928c-b3937fa5b58f",
                    "name": "the last record",
                    "num": None,
                    "an_array": None,
                },
            ],
        }

    def test_download_filtered(self, client, custom_query):
        response = client.post(
            reverse(
                "datasets:custom_dataset_query_data",
                args=(custom_query.dataset.id, custom_query.id),
            )
            + "?download=1",
            data={
                "columns": ["name", "num", "date"],
                "filters": [
                    json.dumps(
                        {
                            "date": {
                                "dateFrom": "2019-12-31 00:00:00",
                                "dateTo": None,
                                "filterType": "date",
                                "type": "greaterThan",
                            }
                        }
                    )
                ],
            },
        )
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == (
            b'"name","num","date"\r\n"the last record","","2020-01-01"\r\n"Number of rows: 1"\r\n'
        )

    def test_download_full(self, client, custom_query):
        response = client.post(
            reverse(
                "datasets:custom_dataset_query_data",
                args=(custom_query.dataset.id, custom_query.id),
            )
            + "?download=1",
            data={"columns": ["name", "num", "date"], "filters": {}},
        )
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == (
            b'"name","num","date"\r\n"the first record",1,""\r\n"the last record","","2020'
            b'-01-01"\r\n"the second record",2,"2019-01-01"\r\n"Number of rows: 3"\r\n'
        )


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_filter_datasets_by_access_search_v2(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    user2 = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - public",
        user_access_type=access_type,
    )
    access_granted_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    factories.DataSetUserPermissionFactory.create(user=user, dataset=access_granted_master)
    factories.DataSetUserPermissionFactory.create(user=user2, dataset=access_granted_master)
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    access_not_granted_datacut = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut - access not granted",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.DataSetUserPermissionFactory.create(user=user2, dataset=access_not_granted_datacut)

    factories.ReferenceDatasetFactory.create(published=True, name="Reference - public")

    access_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.VisualisationUserPermissionFactory(user=user, visualisation=access_vis)
    factories.VisualisationUserPermissionFactory(user=user2, visualisation=access_vis)

    no_access_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - hidden",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.VisualisationUserPermissionFactory(user=user2, visualisation=no_access_vis)

    factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name="Visualisation - public",
        user_access_type=access_type,
    )

    # No access filter set
    response = client.get(reverse("datasets:find_datasets"), {"user_access": []})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 8

    # Find only accessible datasets
    response = client.get(reverse("datasets:find_datasets"), {"user_access": ["yes"]})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 5

    # Find only non-accessible datasets
    response = client.get(reverse("datasets:find_datasets"), {"user_access": ["no"]})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 3

    # Find both accessible and non-accessible datasets
    response = client.get(reverse("datasets:find_datasets"), {"user_access": ["yes", "no"]})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 8


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_filter_reference_datasets_search_v2(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master",
        user_access_type=access_type,
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut",
        user_access_type=access_type,
    )
    factories.ReferenceDatasetFactory.create(published=True, name="Reference")
    response = client.get(
        reverse("datasets:find_datasets"), {"data_type": [DataSetType.REFERENCE]}
    )
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 1


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_filter_bookmarked_search_v2(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER,
        name="Master",
        user_access_type=access_type,
    )
    bookmarked = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT,
        name="Datacut",
        user_access_type=access_type,
    )
    factories.DataSetBookmarkFactory.create(user=user, dataset=bookmarked)

    factories.ReferenceDatasetFactory.create(published=True, name="Reference")
    response = client.get(reverse("datasets:find_datasets"), {"my_datasets": "bookmarked"})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 1


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
@pytest.mark.django_db
def test_filter_data_type_datasets_search_v2(access_type):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    factories.MasterDataSetFactory.create(
        published=True,
        name="Master",
        user_access_type=access_type,
    )
    factories.DatacutDataSetFactory.create(
        published=True,
        name="Datacut",
        user_access_type=access_type,
    )
    factories.ReferenceDatasetFactory.create(published=True, name="Reference")
    response = client.get(reverse("datasets:find_datasets"), {"data_type": [DataSetType.MASTER]})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 1

    response = client.get(reverse("datasets:find_datasets"), {"data_type": [DataSetType.DATACUT]})
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 1

    response = client.get(
        reverse("datasets:find_datasets"), {"data_type": [DataSetType.REFERENCE]}
    )
    assert response.status_code == 200
    assert len(response.context["datasets"]) == 1


@pytest.mark.django_db
def test_find_datasets_filters_show_open_data():
    user = factories.UserFactory.create(is_superuser=True)
    client = Client(**get_http_sso_data(user))

    requires_authorization = factories.DataSetFactory.create(
        name="requires authorization",
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    requires_authentication = factories.DataSetFactory.create(
        name="requires authentication",
        user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    is_open = factories.DataSetFactory.create(name="open", user_access_type=UserAccessType.OPEN)

    response = client.get(reverse("datasets:find_datasets"))

    assert response.status_code == 200
    expected_results = [
        expected_search_result(is_open, has_access=mock.ANY),
        expected_search_result(requires_authentication, has_access=mock.ANY),
        expected_search_result(requires_authorization, has_access=mock.ANY),
    ]

    results = list(response.context["datasets"])
    for expected in expected_results:
        assert expected in results

    assert len(results) == 3

    response = client.get(reverse("datasets:find_datasets"), {"admin_filters": "opendata"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        expected_search_result(is_open, has_access=mock.ANY)
    ]


class TestDatasetEditView:
    def test_only_iam_or_iao_can_edit_dataset(self, client, user):
        dataset = factories.DataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        response = client.get(
            reverse(
                "datasets:edit_dataset",
                args=(dataset.pk,),
            )
        )
        assert response.status_code == 403

        dataset.information_asset_owner = user
        dataset.save()

        response = client.get(
            reverse(
                "datasets:edit_dataset",
                args=(dataset.pk,),
            )
        )
        assert response.status_code == 200

    def test_edit_permissions_page_shows_existing_authorized_users(self, client, user):
        user_1 = factories.UserFactory.create()
        user_2 = factories.UserFactory.create()

        dataset = factories.DataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        dataset.information_asset_owner = user
        dataset.save()
        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user_1)

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200

        assert user_1.email.encode() in response.content
        assert user_2.email.encode() not in response.content

    def test_edit_access_page_shows_iam_iao_flag(self, client, user):
        user_1 = factories.UserFactory.create(
            first_name="Vyvyan",
            last_name="Holland",
            email="vyvyan.holland@businessandtrade.gov.uk",
        )

        dataset = factories.DataSetFactory.create(
            name="Test",
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        dataset.information_asset_owner = user
        dataset.information_asset_manager = user_1
        dataset.save()
        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user_1)

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200

        soup = BeautifulSoup(response.content.decode(response.charset))
        assert f"Manage access to {dataset.name}" in soup.find("h1").contents
        assert "Add user" in soup.find("a", class_="govuk-link").find(
            "button", class_="govuk-button govuk-button--secondary govuk-!-static-margin-bottom-6"
        ).contents[0].get_text(strip=True)
        auth_users = json.loads(response.context_data["authorised_users"])
        assert any(au for au in auth_users if au["iam"] is True and au["id"] == user_1.id)

    def test_edit_access_page_shows_existing_authorized_users(self, client, user):
        user_1 = factories.UserFactory.create(
            first_name="Vyvyan",
            last_name="Holland",
            email="vyvyan.holland@businessandtrade.gov.uk",
        )

        dataset = factories.DataSetFactory.create(
            name="Test",
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        dataset.information_asset_owner = user
        dataset.save()
        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user_1)

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200

        soup = BeautifulSoup(response.content.decode(response.charset))
        assert f"Manage access to {dataset.name}" in soup.find("h1").contents
        auth_users = json.loads(response.context_data["authorised_users"])

        assert [user_1.first_name, user_1.last_name, user_1.email] in [
            [u["first_name"], u["last_name"], u["email"]]
            for u in auth_users
            if user_1.id == u["id"]
        ]
        assert user_1.email.encode() in response.content

    def test_edit_access_page_shows_requesting_users(self, client, user):
        user_1 = factories.UserFactory.create(
            first_name="Vyvyan",
            last_name="Holland",
            email="vyvyan.holland@businessandtrade.gov.uk",
        )
        dataset = factories.DataSetFactory.create(
            name="Test",
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        AccessRequestFactory(
            requester=user_1,
            contact_email=user_1.email,
            catalogue_item_id=dataset.id,
            data_access_status="waiting",
        )
        dataset.information_asset_owner = user
        dataset.save()

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200
        soup = BeautifulSoup(response.content.decode(response.charset))
        td_cell_1 = soup.find_all("td")[0].get_text()
        td_cell_2 = soup.find_all("td")[1]
        review_access_link = td_cell_2.find("a").get("href")
        assert "vyvyan.holland@businessandtrade.gov.uk" in td_cell_1
        assert "Vyvyan Holland" in td_cell_1
        assert "Review access request" in td_cell_2.get_text()
        assert review_access_link == f"/datasets/{dataset.id}/review-access/{user_1.id}"

    def test_add_user_search_shows_relevant_results(self, client, user):
        user_1 = factories.UserFactory.create(email="john@example.com")
        user_2 = factories.UserFactory.create(email="john@example2.com")

        dataset = factories.DataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        dataset.information_asset_owner = user
        dataset.save()
        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200

        soup = BeautifulSoup(response.content.decode(response.charset))
        search_url = soup.findAll("a", href=True, string=re.compile(".*Add users"))[0]["href"]
        response = client.post(search_url, data={"search": "john"}, follow=True)
        assert response.status_code == 200
        assert b"Found 2 matching users" in response.content
        assert user_1.email.encode() in response.content
        assert user_1.first_name.encode() in response.content
        assert user_2.email.encode() in response.content
        assert user_2.first_name.encode() in response.content

    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_remove_removes_user_from_authorized_users_summary(
        self, mock_send_email, client, user
    ):
        user_1 = factories.UserFactory.create(email="john@example.com")

        dataset = factories.DataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
        )
        dataset.information_asset_owner = user
        dataset.save()
        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user_1)

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(dataset.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200
        assert user_1.email.encode() in response.content
        auth_users = json.loads(response.context_data["authorised_users"])
        remove_url = auth_users[0]["remove_user_url"]
        response = client.get(remove_url, follow=True)
        assert response.status_code == 200
        mock_send_email.assert_called_once()
        assert len(json.loads(response.context_data["authorised_users"])) == 2  # iam & iao


class TestVisualisationCatalogueItemEditView:
    def test_only_iam_or_iao_can_edit_visualisation(self, client, user):
        visualisation_catalogue_item = factories.VisualisationCatalogueItemFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )

        response = client.get(
            reverse(
                "datasets:edit_visualisation_catalogue_item",
                args=(visualisation_catalogue_item.pk,),
            )
        )
        assert response.status_code == 403

        visualisation_catalogue_item.information_asset_owner = user
        visualisation_catalogue_item.save()

        response = client.get(
            reverse(
                "datasets:edit_visualisation_catalogue_item",
                args=(visualisation_catalogue_item.pk,),
            )
        )
        assert response.status_code == 200

    def test_edit_permissions_page_shows_existing_authorized_users(self, client, user):
        user_1 = factories.UserFactory.create()
        user_2 = factories.UserFactory.create()

        visualisation_catalogue_item = factories.VisualisationCatalogueItemFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )
        visualisation_catalogue_item.information_asset_owner = user
        visualisation_catalogue_item.information_asset_manager = user
        visualisation_catalogue_item.save()
        factories.VisualisationUserPermissionFactory.create(
            visualisation=visualisation_catalogue_item, user=user_1
        )

        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(visualisation_catalogue_item.pk,),
            ),
            follow=True,
        )
        assert response.status_code == 200

        assert user_1.email.encode() in response.content
        assert user_2.email.encode() not in response.content

    def test_add_user_save_and_continue_creates_visualisation_permissions(self, client, user):
        user_1 = factories.UserFactory.create(email="john@example.com")

        visualisation_catalogue_item = factories.VisualisationCatalogueItemFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )
        visualisation_catalogue_item.information_asset_owner = user
        visualisation_catalogue_item.information_asset_manager = user
        visualisation_catalogue_item.save()
        response = client.get(
            reverse(
                "datasets:edit_permissions",
                args=(visualisation_catalogue_item.pk,),
            )
        )
        assert response.status_code == 302

        summary_page_url = response.get("location")

        response = client.get(summary_page_url)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content.decode(response.charset))
        search_url = soup.findAll("a", href=True, string=re.compile(".*Add user"))[0]["href"]
        response = client.post(search_url, data={"search": "John"}, follow=True)
        assert response.status_code == 200
        assert b"Found 1 matching user" in response.content
        assert user_1.email.encode() in response.content
        assert user_1.first_name.encode() in response.content

        soup = BeautifulSoup(response.content.decode(response.charset))
        action = soup.find("form", {"action": True}).get("action")
        response = client.get(action, follow=True)
        assert response.status_code == 200
        assert user_1.email.encode() in response.content

        assert len(VisualisationUserPermission.objects.all()) == 0
        response = client.post(summary_page_url)
        assert (
            len(VisualisationUserPermission.objects.all()) == 2
        )  # iam and iao permissions created on summary page

        assert (
            VisualisationUserPermission.objects.all()[0].visualisation
            == visualisation_catalogue_item
        )
        assert set(vup.user for vup in VisualisationUserPermission.objects.all()) == set(
            [user, user_1]
        )


class TestDatasetManagerViews:
    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @pytest.mark.django_db
    def test_linked_to_pipeline_page(self, client, user):
        dataset_1 = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
        )
        source_1 = factories.SourceTableFactory.create(
            dataset=dataset_1, schema="test", table="sql_table1"
        )

        dataset_2 = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
        )
        source_2 = factories.SourceTableFactory.create(
            dataset=dataset_2, schema="test", table="sharepoint_table2"
        )

        url_1 = reverse("datasets:manager:manage-source-table", args=(dataset_1.id, source_1.id))
        dataset_1.information_asset_manager = user
        dataset_1.save()

        url_2 = reverse("datasets:manager:manage-source-table", args=(dataset_2.id, source_2.id))
        dataset_2.information_asset_manager = user
        dataset_2.save()

        response = client.get(url_1)
        assert response.status_code == 200
        content = response.content.decode(response.charset)
        assert "Manage pipeline" not in content

        factories.PipelineFactory.create(type="sharepoint", table_name="schema.sql_table1")
        response = client.get(url_1)
        content = response.content.decode(response.charset)
        assert "Manage pipeline" not in content

        factories.PipelineFactory.create(type="sql", table_name="test.sql_table1")
        response = client.get(url_1)
        content = response.content.decode(response.charset)
        assert "Manage pipeline" in content

        # The pipelines page has elements with the ID of the pipeline,
        # And we assert that we link to the right pipeline.
        assert "#test.sql_table1" in content

        factories.PipelineFactory.create(type="sharepoint", table_name="test.sharepoint_table2")
        response = client.get(url_2)
        content = response.content.decode(response.charset)
        assert "Manage pipeline" in content

        # The pipelines page has elements with the ID of the pipeline,
        # And we assert that we link to the right pipeline.
        assert "#test.sharepoint_table2" in content

    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @pytest.mark.django_db
    def test_update_restore_page(self, client, user):
        UploadedTable.objects.create(
            schema="test",
            table_name="table1",
            data_flow_execution_date=datetime(2022, 1, 1),
        )
        UploadedTable.objects.create(
            schema="test",
            table_name="table2",
            data_flow_execution_date=datetime(2022, 1, 1),
        )
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
        )
        source = factories.SourceTableFactory.create(
            dataset=dataset, schema="test", table="table1"
        )

        url = reverse("datasets:manager:manage-source-table", args=(dataset.id, source.id))

        # User is not IAM
        response = client.get(url)
        assert response.status_code == 403

        # User is IAM
        dataset.information_asset_manager = user
        dataset.save()
        response = client.get(url)
        response.status_code = 200
        assert "Upload a new CSV to this table" in response.content.decode(response.charset)
        assert len(response.context["source"].get_previous_uploads()) == 1

    @freeze_time("2021-01-01 01:01:01")
    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @override_settings(NOTEBOOKS_BUCKET="notebooks-bucket")
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.datasets.manager.views.uuid.uuid4")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    @mock.patch("dataworkspace.apps.datasets.manager.views.get_s3_prefix")
    def test_csv_upload(
        self,
        mock_get_s3_prefix,
        mock_upload_to_clamav,
        mock_boto_client,
        mock_uuid,
        client,
        user,
    ):
        file_uuid = "39dde835-6551-47c0-863f-7600a1ef93a3"
        file_name = f"file1.csv!{file_uuid}"
        mock_uuid.return_value = file_uuid
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})
        source = factories.SourceTableFactory.create(
            dataset=factories.MasterDataSetFactory.create(
                published=True,
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
                information_asset_manager=user,
                enquiries_contact=user,
            ),
            schema="test",
            table="table1",
        )
        file1 = SimpleUploadedFile(
            "file1.csv",
            b"id,name\r\nA1,test1\r\nA2,test2\r\n",
            content_type="text/csv",
        )

        response = client.post(
            reverse(
                "datasets:manager:manage-source-table",
                args=(source.dataset.id, source.id),
            ),
            data={"csv_file": file1},
        )
        assert response.status_code == 302
        assert (
            response["Location"]
            == reverse(
                "datasets:manager:manage-source-table-column-config",
                args=(source.dataset_id, source.id),
            )
            + f"?file={file_name}"
        )
        mock_boto_client().put_object.assert_called_once_with(
            Body=mock.ANY,
            Bucket="notebooks-bucket",
            Key=f"user/federated/abc/_source_table_uploads/{source.id}/{file_name}",
        )

    @freeze_time("2021-01-01 01:01:01")
    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.datasets.manager.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.datasets.manager.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.datasets.manager.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.datasets.manager.views.get_s3_prefix")
    def test_column_config(
        self,
        mock_get_s3_prefix,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        client,
        user,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_trigger_dag.return_value = {"execution_date": datetime.now()}
        mock_get_column_types.return_value = [
            {
                "header_name": "ID",
                "column_name": "id",
                "data_type": "text",
                "sample_data": ["a", "b", "c"],
            },
            {
                "header_name": "name",
                "column_name": "name",
                "data_type": "text",
                "sample_data": ["d", "e", "f"],
            },
        ]

        source = factories.SourceTableFactory.create(
            dataset=factories.MasterDataSetFactory.create(
                published=True,
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
                information_asset_manager=user,
            ),
            schema="test",
            table="table1",
        )
        response = client.post(
            reverse(
                "datasets:manager:manage-source-table-column-config",
                args=(source.dataset.id, source.id),
            )
            + "?file=file1.csv",
            data={
                "path": "user/federated/abc/file1.csv",
                "id": "text",
                "name": "text",
            },
        )
        assert response.status_code == 302
        assert (
            response["Location"]
            == reverse(
                "datasets:manager:upload-validating",
                args=(source.dataset_id, source.id),
            )
            + f"?filename=file1.csv&schema={source.schema}&table_name={source.table}&"
            f"execution_date=2021-01-01+01%3A01%3A01"
        )
        mock_copy_file.assert_called_with(
            "user/federated/abc/file1.csv",
            "data-flow-imports/user/federated/abc/file1.csv",
        )
        mock_trigger_dag.assert_called_with(
            {
                "file_path": "data-flow-imports/user/federated/abc/file1.csv",
                "schema_name": source.schema,
                "table_name": source.table,
                "column_definitions": mock_get_column_types.return_value,
                "auto_generate_id_column": False,
            },
            "DataWorkspaceS3ImportPipeline",
            "test-table1-2021-01-01T01:01:01",
        )

    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @pytest.mark.django_db
    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.datasets.manager.views.trigger_dataflow_dag")
    def test_restore_table(self, mock_trigger_dag, dataset_db_with_swap_table, user, client):
        mock_trigger_dag.return_value = {"execution_date": "2022-01-01"}
        version = UploadedTable.objects.create(
            schema="public",
            table_name="dataset_test",
            data_flow_execution_date=datetime(2022, 1, 1),
        )
        source = factories.SourceTableFactory.create(
            dataset=factories.MasterDataSetFactory.create(
                published=True,
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
                information_asset_manager=user,
            ),
            schema="public",
            table="dataset_test",
        )
        response = client.post(
            reverse(
                "datasets:manager:restore-table",
                args=(source.dataset.id, source.id, version.id),
            )
        )
        assert response.status_code == 302
        assert (
            response["Location"]
            == reverse(
                "datasets:manager:restoring-table",
                args=(source.dataset_id, source.id, version.id),
            )
            + "?execution_date=2022-01-01&task_name=restore-swap-table-datasets_db"
        )
        mock_trigger_dag.assert_called_with(
            {
                "ts_nodash": "20220101t000000",
                "schema_name": "public",
                "table_name": "dataset_test",
            },
            "DataWorkspaceRestoreTablePipeline",
            "restore-public-dataset_test-2021-01-01T01:01:01",
        )

    @override_flag(settings.DATA_UPLOADER_UI_FLAG, active=True)
    @pytest.mark.django_db
    @freeze_time("2021-01-01 01:01:01")
    @pytest.mark.parametrize(
        "log_message,expected_text",
        [
            (
                "is of type bigint but expression is of type boolean",
                b"There's an error in a column which has been set as: 'Integer'",
            ),
            (
                "is of type numeric but expression is of type boolean",
                b"There's an error in a column which has been set as: 'Numeric'",
            ),
            (
                "is of type date but expression is of type boolean",
                b"There's an error in a column which has been set as: 'Date'",
            ),
            (
                "is of type timestamp with time zone but expression is of type boolean",
                b"There's an error in a column which has been set as: 'Datetime'",
            ),
            ("Not a boolean value", b"Your CSV contains a value that cannot be set as 'Boolean'"),
            (
                "invalid input syntax for type bigint",
                b"Your CSV contains a 'String' value that cannot be set as 'Integer'",
            ),
            (
                "invalid input syntax for type numeric",
                b"Your CSV contains a 'String' value that cannot be set as 'Numeric'",
            ),
            ("is of type date", b"There's an error in a column which has been set as: 'Date'"),
            (
                "invalid input syntax for type date",
                b"There's an error in a column which has been set as: 'Date'",
            ),
            (
                "is of type timestamp",
                b"There's an error in a column which has been set as: 'Datetime'",
            ),
            (
                "invalid input syntax for type timestamp",
                b"There's an error in a column which has been set as: 'Datetime'",
            ),
            (
                "date/time field value out of range",
                b"Your CSV contains a date that cannot be correct",
            ),
            ("some other error", b"There's a problem with your CSV"),
        ],
    )
    @mock.patch("dataworkspace.apps.core.utils.get_dataflow_task_log")
    def test_upload_failed_view(
        self,
        mock_get_task_log,
        log_message,
        expected_text,
        dataset_db_with_swap_table,
        user,
        client,
    ):
        mock_get_task_log.return_value = (
            f"Dummy logging output...\n{log_message}\nmore log output\nEND"
        )
        source = factories.SourceTableFactory.create(
            dataset=factories.MasterDataSetFactory.create(
                published=True,
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
                information_asset_manager=user,
            ),
            schema="public",
            table="dataset_test",
        )
        response = client.get(
            reverse(
                "datasets:manager:upload-failed",
                args=(
                    source.dataset.id,
                    source.id,
                ),
            )
            + "?filename=test.csv&execution_date=2022-01-01&task_name=dummy"
        )
        assert response.status_code == 200
        assert expected_text in response.content


class TestSaveDataGridView:
    @pytest.mark.parametrize(
        "source_factory",
        [
            factories.SourceTableFactory,
            factories.CustomDatasetQueryFactory,
            factories.ReferenceDatasetFactory,
        ],
    )
    def test_update(self, user, client, source_factory):
        source = source_factory.create()
        view = factories.UserDataTableViewFactory(
            user=user,
            source_object_id=str(source.id),
            source_content_type=ContentType.objects.get_for_model(source),
            filters={"col1": {"value": "test filter"}},
            column_defs=[{"col1": {"field": "col1", "position": 0, "visible": True}}],
        )
        response = client.post(
            source.get_save_grid_view_url(),
            content_type="application/json",
            data={
                "visibleColumns": ["col3"],
                "filters": None,
                "columnDefs": [{"field": "col1", "position": 1, "visible": False}],
            },
        )
        assert response.status_code == 200
        view.refresh_from_db()
        assert view.grid_config() == {
            "filters": None,
            "columnDefs": {"col1": {"field": "col1", "position": 1, "visible": False}},
        }

    @pytest.mark.parametrize(
        "source_factory",
        [
            factories.SourceTableFactory,
            factories.CustomDatasetQueryFactory,
            factories.ReferenceDatasetFactory,
        ],
    )
    def test_create(self, user, client, source_factory):
        source = source_factory.create()
        response = client.post(
            source.get_save_grid_view_url(),
            content_type="application/json",
            data={
                "filters": {"a": "test"},
                "columnDefs": [{"field": "col1", "position": 1, "visible": False}],
            },
        )
        assert response.status_code == 200
        view = UserDataTableView.objects.first()
        assert view.user == user
        assert view.grid_config() == {
            "filters": {"a": "test"},
            "columnDefs": {"col1": {"field": "col1", "position": 1, "visible": False}},
        }

    @pytest.mark.parametrize(
        "source_factory",
        [
            factories.SourceTableFactory,
            factories.CustomDatasetQueryFactory,
            factories.ReferenceDatasetFactory,
        ],
    )
    def test_delete(self, user, client, source_factory):
        source = source_factory.create()
        factories.UserDataTableViewFactory(
            user=user,
            source_object_id=str(source.id),
            source_content_type=ContentType.objects.get_for_model(source),
            filters={"col1": {"value": "test filter"}},
            column_defs=[{"col1": {"field": "col1", "position": 0, "visible": True}}],
        )
        view_count = UserDataTableView.objects.count()
        response = client.delete(
            source.get_save_grid_view_url(),
        )
        assert response.status_code == 200
        assert UserDataTableView.objects.count() == view_count - 1


@pytest.mark.django_db
def test_master_dataset_detail_page_shows_pipeline_failures(client, metadata_db):
    dataset = factories.DataSetFactory.create(
        type=DataSetType.MASTER,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    factories.SourceTableFactory(
        dataset=dataset, database=metadata_db, schema="public", table="table1"
    )
    factories.SourceTableFactory(
        dataset=dataset, database=metadata_db, schema="public", table="table2"
    )

    url = reverse("datasets:dataset_detail", args=(dataset.id,))
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["show_pipeline_failed_message"]
    assert (
        len(
            [
                x
                for x in response.context["master_datasets_info"]
                if not x.pipeline_last_run_succeeded
            ]
        )
        == 1
    )
    assert (
        len([x for x in response.context["master_datasets_info"] if x.pipeline_last_run_succeeded])
        == 1
    )


class TestDatasetReviewAccess:
    def setUp(self, eligibility_criteria=False, eligibility_criteria_met=True):
        criteria = [eligibility_criteria] if eligibility_criteria else None
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        self.user_requestor = factories.UserFactory.create(
            first_name="Bob",
            last_name="Testerten",
            email="bob.testerten@contact-email.com",
            is_superuser=False,
        )
        self.dataset = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="Master",
            eligibility_criteria=criteria,
        )
        AccessRequestFactory(
            id=self.user_requestor.id,
            requester_id=self.user_requestor.id,
            catalogue_item_id=self.dataset.id,
            contact_email=self.user_requestor.email,
            reason_for_access="I need it",
            eligibility_criteria_met=eligibility_criteria_met,
        )

    def assert_common(self, include_eligibility_requirements=False):
        response = self.client.get(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            )
        )
        soup = BeautifulSoup(response.content.decode(response.charset))
        header_one = soup.find("h1")
        requester_section_header = header_one.find_next_sibling("h2")
        requester_section_name = requester_section_header.find_next_sibling("p")
        requester_reason_section_header = soup.find_all("h2")[1]
        requester_reason_section_reason = requester_reason_section_header.find_next_sibling("p")

        form = soup.find("form")
        form_legend = form.find("legend")
        label_grant = form.find_all("label")[0]
        label_deny = form.find_all("label")[1]
        label_why_deny = form.find_all("label")[2]
        [input_grant] = form.find("input", {"id": "id_action_type_0"}).get_attribute_list("value")
        [input_deny] = form.find("input", {"id": "id_action_type_1"}).get_attribute_list("value")
        form.find("textarea", {"id": "id_message"})

        assert response.status_code == 200
        assert header_one.get_text() == "Review Bob Testerten's access to Master"
        assert requester_section_header.get_text() == "Requestor"
        assert requester_section_name.get_text() == "Bob Testertenbob.testerten@contact-email.com"
        assert requester_reason_section_header.get_text() == "Requestor's reason for access"
        assert requester_reason_section_reason.get_text() == "I need it"

        assert form_legend.find("h2").get_text() == "Actions you can take"
        assert label_grant.get_text() == "Grant Bob Testerten access to this dataset"
        assert input_grant == "grant"
        assert label_deny.get_text() == "Deny Bob Testerten access to this dataset"
        assert input_deny == "other"
        assert "Why are you denying access to this data?" in label_why_deny.get_text()
        if include_eligibility_requirements:
            self.assert_eligibility_requirements_details(soup)

        return [soup, response]

    def assert_eligibility_requirements_details(self, soup):
        eligibility_requirements_summary = soup.find("summary")
        eligibility_requirements_reason = eligibility_requirements_summary.find_next_sibling(
            "div"
        ).find_next("p")
        assert (
            "Eligibility requirements needed to access this data"
            in eligibility_requirements_summary.get_text()
        )
        assert eligibility_requirements_reason.get_text() == "You need to be eligible"

    @pytest.mark.django_db
    def test_user_has_met_eligibility_requirements(self):
        self.setUp("You need to be eligible")
        [soup, _] = self.assert_common()
        self.assert_eligibility_requirements_details(soup)
        requesters_eligibility_requirements_answer = soup.find("details").find_next_sibling("p")
        assert (
            requesters_eligibility_requirements_answer.get_text()
            == "The requestor answered that they do meet the eligibility requirements"
        )

    @pytest.mark.django_db
    def test_user_has_not_met_eligibility_requirements(self):
        self.setUp("You need to be eligible", eligibility_criteria_met=False)
        [soup, _] = self.assert_common()
        self.assert_eligibility_requirements_details(soup)
        requesters_eligibility_requirements_answer = soup.find("details").find_next_sibling("p")
        requesters_eligibility_override_message = (
            requesters_eligibility_requirements_answer.find_next_sibling("p")
        )
        assert (
            requesters_eligibility_requirements_answer.get_text()
            == "The requestor answered that they do not meet the eligibility requirements"
        )
        assert (
            requesters_eligibility_override_message.get_text()
            == "You can still grant them access if they have a good reason for it."
        )

    @pytest.mark.django_db
    def test_dataset_does_not_have_eligibility_requirements(self):
        self.setUp()
        [_, response] = self.assert_common()
        assert "Have the eligibility requirements been met?" not in response.content.decode(
            response.charset
        )


@pytest.mark.django_db
class TestDatasetReviewAccessApproval:
    def setUp(self, is_visualisation=False, name="Master", dataset_type=DataSetType.MASTER):
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        self.user_requestor = factories.UserFactory.create(
            first_name="Bob",
            last_name="Testerten",
            email="bob.testerten@contact-email.com",
            is_superuser=False,
        )
        if not is_visualisation:
            self.dataset = factories.DataSetFactory.create(
                published=True,
                type=dataset_type,
                name=name,
                eligibility_criteria=["you must be eligible"],
            )
            self.accessRequest = AccessRequestFactory(
                id=self.user_requestor.id,
                requester_id=self.user_requestor.id,
                catalogue_item_id=self.dataset.id,
                contact_email=self.user_requestor.email,
                reason_for_access="I need it",
                eligibility_criteria_met=True,
            )
        else:
            user_iam = factories.UserFactory.create(
                first_name="Frank",
                last_name="Example",
                email="frank.example@contact-email.com",
                is_superuser=False,
            )
            user_iao = factories.UserFactory.create(
                first_name="Roberta",
                last_name="Powell",
                email="roberta.powell@contact-email.com",
                is_superuser=False,
            )
            self.dataset = factories.VisualisationCatalogueItemFactory.create(
                published=True,
                name="Visualisation",
                information_asset_manager=user_iam,
                information_asset_owner=user_iao,
            )
            AccessRequestFactory(
                id=self.user_requestor.id,
                requester_id=self.user_requestor.id,
                catalogue_item_id=self.dataset.id,
                contact_email=self.user_requestor.email,
                reason_for_access="I need it",
            )

    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_master_dataset_approval_with_email_sent(self, mock_send_email):
        self.setUp()
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "grant"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Master",
                "dataset_url": f"http://testserver/datasets/{self.dataset.id}",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know they now have access."
            in success_message
        )

    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_datacut_dataset_approval_with_email_sent(self, mock_send_email):
        self.setUp(name="Datacut", dataset_type=DataSetType.DATACUT)
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "grant"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Datacut",
                "dataset_url": f"http://testserver/datasets/{self.dataset.id}",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know they now have access."
            in success_message
        )

    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_visualisation_dataset_approval_with_email_sent(self, mock_send_email):
        self.setUp(is_visualisation=True)
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "grant"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Visualisation",
                "dataset_url": f"http://testserver/datasets/{self.dataset.id}",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know they now have access."
            in success_message
        )

    @override_settings(ENVIRONMENT="Production")
    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    def test_master_dataset_access_denied_with_email_sent(self, mock_send_email):
        self.setUp()
        factories.PendingAuthorizedUsersFactory.create(
            id="1", users='["6"]', created_by_id=self.user.id
        )
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "other", "message": "Because no"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()

        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_DENIED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Master",
                "deny_reasoning": "Because no",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know their access request was not successful."
            in success_message
        )

    @override_settings(ENVIRONMENT="Production")
    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    def test_datacut_dataset_access_denied_with_email_sent(self, mock_send_email):
        self.setUp(name="Datacut", dataset_type=DataSetType.DATACUT)
        factories.PendingAuthorizedUsersFactory.create(
            id="1", users='["6"]', created_by_id=self.user.id
        )
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "other", "message": "Because no"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_DENIED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Datacut",
                "deny_reasoning": "Because no",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know their access request was not successful."
            in success_message
        )

    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_visualisation_dataset_access_denied_with_email_sent(self, mock_send_email):
        self.setUp(is_visualisation=True)
        factories.PendingAuthorizedUsersFactory.create(
            id="1", users='["6"]', created_by_id=self.user.id
        )
        response = self.client.post(
            reverse(
                "datasets:review_access",
                kwargs={"pk": self.dataset.id, "user_id": self.user_requestor.id},
            ),
            {"action_type": "other", "message": "Because no"},
        )
        redirect_response = self.client.get(response.url)
        soup = BeautifulSoup(redirect_response.content.decode(redirect_response.charset))
        notification_banner = soup.find("div", attrs={"data-module", "govuk-notification-banner"})
        success_header = notification_banner.find_next("h2").get_text()
        success_message = notification_banner.find_next("p").get_text()
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_DENIED_TEMPLATE_ID,
            self.user_requestor.email,
            personalisation={
                "email_address": self.user_requestor.email,
                "dataset_name": "Visualisation",
                "deny_reasoning": "Because no",
            },
        )
        assert response.status_code == 302
        assert redirect_response.status_code == 200
        assert "Success" in success_header
        assert (
            "An email has been sent to Bob Testerten to let them know their access request was not successful."
            in success_message
        )


@pytest.mark.django_db
class TestDatasetAddAuthorisedUserView:
    @mock.patch("dataworkspace.apps.datasets.views.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_user_gets_added_to_dataset_and_gets_emailed(self, mock_send_email):
        user = factories.UserFactory.create(is_superuser=True)
        client = Client(**get_http_sso_data(user))
        user_requestor = factories.UserFactory.create(
            first_name="Bob",
            last_name="Testerten",
            email="bob.testerten@contact-email.com",
            is_superuser=False,
        )

        dataset = factories.DataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            type=DataSetType.MASTER,
            name="Master",
        )

        factories.PendingAuthorizedUsersFactory.create(
            id="1", users='["6"]', created_by_id=user.id
        )

        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user)

        client.post(
            reverse(
                "datasets:add_authorized_user",
                kwargs={"pk": dataset.id, "user_id": user_requestor.id, "summary_id": "1"},
            ),
        )

        assert dataset.datasetuserpermission_set.filter(user=user_requestor).exists() is True
        mock_send_email.assert_called_with(
            settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
            user_requestor.email,
            personalisation={
                "email_address": user_requestor.email,
                "dataset_name": dataset.name,
                "dataset_url": f"http://testserver/datasets/{dataset.id}",
            },
        )


@pytest.mark.django_db
class TestDatasetEditPermissionsSummaryView:
    def setUp(self, email="bob.testerten@contact-email.com"):
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        self.user_requestor = factories.UserFactory.create(
            first_name="Bob",
            last_name="Testerten",
            email="bob.testerten@contact-email.com",
            is_superuser=False,
        )
        self.dataset = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER,
            name="Master",
        )
        AccessRequestFactory(
            id=self.user_requestor.id,
            requester_id=self.user_requestor.id,
            catalogue_item_id=self.dataset.id,
            contact_email=email,
            reason_for_access="I need it",
            eligibility_criteria_met=True,
            data_access_status="waiting",
        )
        factories.PendingAuthorizedUsersFactory.create(
            id="1", users=f"[{self.user_requestor.id}]", created_by_id=self.user.id
        )

    def test_access_requests_display_when_pending_users_exist(self):
        self.setUp()
        response = self.client.get(
            reverse(
                "datasets:edit_permissions_summary",
                args=[
                    self.dataset.id,
                    "1",
                ],
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))

        user_access_request_header = soup.find("h2").text
        user_access_request = soup.find("td").text

        assert user_access_request_header == "Users who have requested access"
        assert "bob.testerten@contact-email.com" in user_access_request

    @mock.patch("logging.Logger.error")
    def test_access_requests_do_not_display_when_non_users_exist(self, mock_logger):
        self.setUp(email="bob.testerten@some-email.com")
        response = self.client.get(
            reverse(
                "datasets:edit_permissions_summary",
                args=[
                    self.dataset.id,
                    "1",
                ],
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))

        main = soup.find("main").text

        assert "Users who have requested access" not in main
        assert "bob.testerten@some-email.com" not in main
        assert mock_logger.call_args_list == [
            mock.call("User with email: %s no longer exists.", "bob.testerten@some-email.com")
        ]
