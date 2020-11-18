from datetime import timedelta, date
import random
from urllib.parse import quote_plus
from uuid import uuid4

import mock
import psycopg2
import pytest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import Client
from lxml import html
from waffle.models import Flag

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    VisualisationCatalogueItem,
)
from dataworkspace.apps.datasets.views import (
    get_datasets_data_for_user_matching_query,
    get_visualisations_data_for_user_matching_query,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data, MatchUnorderedMembers
from dataworkspace.tests.factories import (
    VisualisationCatalogueItemFactory,
    UserFactory,
    VisualisationUserPermissionFactory,
    VisualisationLinkFactory,
)
from dataworkspace.utils import DATA_EXPLORER_FLAG


@pytest.mark.parametrize(
    'eligibility_criteria,view_name',
    [
        ([], 'datasets:request_access'),
        (['Criteria 1', 'Criteria 2'], 'datasets:eligibility_criteria'),
    ],
)
def test_dataset_has_request_access_link(
    client, eligibility_criteria, view_name, metadata_db
):
    ds = factories.DataSetFactory.create(
        eligibility_criteria=eligibility_criteria, published=True
    )

    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    request_access_url = reverse(view_name, args=[ds.id])

    assert response.status_code == 200
    assert request_access_url in str(response.content)


def test_eligibility_criteria_list(client):
    ds = factories.DataSetFactory.create(
        eligibility_criteria=['Criteria 1', 'Criteria 2'], published=True
    )

    response = client.get(
        reverse('datasets:eligibility_criteria', kwargs={'dataset_uuid': ds.id})
    )

    assert response.status_code == 200
    assert 'Criteria 1' in str(response.content)
    assert 'Criteria 2' in str(response.content)


@pytest.mark.parametrize(
    'meet_criteria,redirect_view',
    [
        ('yes', 'datasets:request_access'),
        ('no', 'datasets:eligibility_criteria_not_met'),
    ],
)
def test_submit_eligibility_criteria(client, test_case, meet_criteria, redirect_view):
    ds = factories.DataSetFactory.create(
        eligibility_criteria=['Criteria 1', 'Criteria 3'], published=True
    )

    response = client.post(
        reverse('datasets:eligibility_criteria', kwargs={'dataset_uuid': ds.id}),
        data={"meet_criteria": meet_criteria},
        follow=True,
    )

    test_case.assertRedirects(
        response, reverse(redirect_view, kwargs={'dataset_uuid': ds.id})
    )


def test_request_access_form(client, mocker):
    create_zendesk_ticket = mocker.patch(
        'dataworkspace.apps.datasets.views.create_zendesk_ticket'
    )
    create_zendesk_ticket.return_value = 999

    ds = factories.DataSetFactory.create(published=True)
    log_count = EventLog.objects.count()

    response = client.post(
        reverse('datasets:request_access', kwargs={'dataset_uuid': ds.id}),
        data={"email": "user@example.com", "goal": "My goal"},
        follow=True,
    )

    assert response.status_code == 200

    create_zendesk_ticket.assert_called_once_with(
        "user@example.com", mock.ANY, "My goal", mock.ANY, ds.name, mock.ANY, None, None
    )
    assert EventLog.objects.count() == log_count + 1
    assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_ACCESS_REQUEST


def test_request_gitlab_visualisation_access(client, user, mocker):
    owner = factories.UserFactory()
    secondary_contact = factories.UserFactory()

    create_zendesk_ticket = mocker.patch(
        'dataworkspace.apps.datasets.views.create_support_request'
    )
    create_zendesk_ticket.return_value = 123

    send_email = mocker.patch('dataworkspace.apps.datasets.views.send_email')

    ds = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        enquiries_contact=owner,
        secondary_enquiries_contact=secondary_contact,
        visualisation_template__gitlab_project_id=321,
    )

    response = client.post(
        reverse('datasets:request_access', kwargs={'dataset_uuid': ds.id}),
        data={"email": "user@example.com", "goal": "my goal"},
        follow=True,
    )

    assert response.status_code == 200

    create_zendesk_ticket.assert_called_once_with(
        mock.ANY,
        mock.ANY,
        mock.ANY,
        subject=f"Data visualisation access request received - {ds.name}",
        tag="visualisation-access-request",
    )

    send_email.assert_has_calls(
        [
            mock.call(
                mock.ANY,
                owner.email,
                personalisation={
                    "visualisation_name": ds.name,
                    "visualisation_url": f"http://testserver/datasets/{ds.id}#{ds.slug}",
                    "user_email": "user@example.com",
                    "people_url": "https://people.trade.gov.uk/search?search_filters[]=people&query=Frank%20Exampleson",
                    "give_access_url": mock.ANY,
                    "goal": "my goal",
                },
            ),
            mock.call(
                mock.ANY,
                secondary_contact.email,
                personalisation={
                    "visualisation_name": ds.name,
                    "visualisation_url": f"http://testserver/datasets/{ds.id}#{ds.slug}",
                    "user_email": "user@example.com",
                    "people_url": "https://people.trade.gov.uk/search?search_filters[]=people&query=Frank%20Exampleson",
                    "give_access_url": mock.ANY,
                    "goal": "my goal",
                },
            ),
        ],
        any_order=True,
    )


def test_request_non_gitlab_visualisation_access(client, user, mocker):
    owner = factories.UserFactory()
    secondary_contact = factories.UserFactory()
    create_zendesk_ticket = mocker.patch(
        'dataworkspace.apps.datasets.views.create_zendesk_ticket'
    )
    create_zendesk_ticket.return_value = 999

    ds = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        enquiries_contact=owner,
        secondary_enquiries_contact=secondary_contact,
        user_access_type='REQUIRES_AUTHORIZATION',
        visualisation_template=None,
    )
    VisualisationLinkFactory.create(
        visualisation_type='DATASTUDIO',
        visualisation_catalogue_item=ds,
        name='Visualisation datastudio',
        identifier='https://www.data.studio.test',
    )

    response = client.post(
        reverse('datasets:request_access', kwargs={'dataset_uuid': ds.id}),
        data={"email": "user@example.com", "goal": "My goal"},
        follow=True,
    )

    assert response.status_code == 200

    create_zendesk_ticket.assert_called_once_with(
        "user@example.com", mock.ANY, "My goal", mock.ANY, ds.name, mock.ANY, None, None
    )


def test_find_datasets_with_no_results(client):
    response = client.get(reverse('datasets:find_datasets'), {"q": "search"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == []

    assert b"There are no results for your search" in response.content


def test_find_datasets_combines_results(client):
    factories.DataSetFactory.create(published=False, name='Unpublished search dataset')
    ds = factories.DataSetFactory.create(published=True, name='A search dataset')
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A search reference dataset'
    )
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A search visualisation'
    )

    response = client.get(reverse('datasets:find_datasets'), {"q": "search"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
        {
            'id': vis.id,
            'name': vis.name,
            'slug': vis.slug,
            'search_rank': mock.ANY,
            'short_description': vis.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'published': True,
            'has_access': True,
        },
    ]

    assert "If you haven’t found what you’re looking for" in response.content.decode(
        response.charset
    )


def test_find_datasets_filters_by_query(client):
    factories.DataSetFactory.create(published=True, name='A dataset')
    factories.ReferenceDatasetFactory.create(published=True, name='A reference dataset')
    factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A visualisation'
    )

    ds = factories.DataSetFactory.create(published=True, name='A new dataset')
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A new visualisation'
    )

    response = client.get(reverse('datasets:find_datasets'), {"q": "new"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
        {
            'id': vis.id,
            'name': vis.name,
            'slug': vis.slug,
            'search_rank': mock.ANY,
            'short_description': vis.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'published': True,
            'has_access': True,
        },
    ]


def test_find_datasets_filters_by_use(client):
    factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    ds = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )

    response = client.get(reverse('datasets:find_datasets'), {"use": [0, 2]})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
    ]


def test_find_datasets_filters_visualisations_by_use(client):
    factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    ds = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A new visualisation'
    )

    response = client.get(reverse('datasets:find_datasets'), {"use": [2, 3]})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': vis.id,
            'name': vis.name,
            'slug': vis.slug,
            'search_rank': mock.ANY,
            'short_description': vis.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'published': True,
            'has_access': True,
        },
    ]


def test_find_datasets_filters_by_source(client):
    source = factories.SourceTagFactory()
    source_2 = factories.SourceTagFactory()
    # Create another SourceTag that won't be associated to a dataset
    factories.SourceTagFactory()

    _ds = factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    _ds.source_tags.set([factories.SourceTagFactory()])

    _vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A visualisation'
    )

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=_vis.visualisation_template, dataset=_ds
    )

    ds = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    ds.source_tags.set([source, source_2])

    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    rds.source_tags.set([source])

    vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A new visualisation'
    )

    factories.DataSetApplicationTemplatePermissionFactory(
        application_template=vis.visualisation_template, dataset=ds
    )

    response = client.get(reverse('datasets:find_datasets'), {"source": [source.id]})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': 0.0,
            'short_description': ds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': MatchUnorderedMembers([source.name, source_2.name]),
            'source_tag_ids': MatchUnorderedMembers([source.id, source_2.id]),
            'purpose': ds.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': 0.0,
            'short_description': rds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': [source.name],
            'source_tag_ids': [source.id],
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
    ]

    assert len(list(response.context["form"].fields['source'].choices)) == 3


def test_find_datasets_order_by_name_asc(client):
    ds1 = factories.DataSetFactory.create(name='a dataset')
    rds = factories.ReferenceDatasetFactory.create(name='b reference dataset')
    vis = factories.VisualisationCatalogueItemFactory.create(name='c visualisation')

    response = client.get(reverse('datasets:find_datasets'), {"sort": "name"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds1.id,
            'name': ds1.name,
            'slug': ds1.slug,
            'search_rank': mock.ANY,
            'short_description': ds1.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds1.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'has_access': True,
        },
        {
            'id': vis.id,
            'name': vis.name,
            'slug': vis.slug,
            'search_rank': mock.ANY,
            'short_description': vis.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'has_access': True,
        },
    ]


def test_find_datasets_order_by_newest_first(client):
    ads1 = factories.DataSetFactory.create(published_at=date.today())
    ads2 = factories.DataSetFactory.create(
        published_at=date.today() - timedelta(days=3)
    )
    ads3 = factories.DataSetFactory.create(
        published_at=date.today() - timedelta(days=4)
    )

    response = client.get(reverse('datasets:find_datasets'), {"sort": "-published_at"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ads1.id,
            'name': ads1.name,
            'slug': ads1.slug,
            'search_rank': mock.ANY,
            'short_description': ads1.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads1.type,
            'has_access': False,
        },
        {
            'id': ads2.id,
            'name': ads2.name,
            'slug': ads2.slug,
            'search_rank': mock.ANY,
            'short_description': ads2.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads2.type,
            'has_access': False,
        },
        {
            'id': ads3.id,
            'name': ads3.name,
            'slug': ads3.slug,
            'search_rank': mock.ANY,
            'short_description': ads3.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads3.type,
            'has_access': False,
        },
    ]


def test_find_datasets_order_by_oldest_first(client):
    ads1 = factories.DataSetFactory.create(
        published_at=date.today() - timedelta(days=1)
    )
    ads2 = factories.DataSetFactory.create(
        published_at=date.today() - timedelta(days=2)
    )
    ads3 = factories.DataSetFactory.create(
        published_at=date.today() - timedelta(days=3)
    )

    response = client.get(reverse('datasets:find_datasets'), {"sort": "published_at"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ads3.id,
            'name': ads3.name,
            'slug': ads3.slug,
            'search_rank': mock.ANY,
            'short_description': ads3.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads3.type,
            'has_access': False,
        },
        {
            'id': ads2.id,
            'name': ads2.name,
            'slug': ads2.slug,
            'search_rank': mock.ANY,
            'short_description': ads2.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads2.type,
            'has_access': False,
        },
        {
            'id': ads1.id,
            'name': ads1.name,
            'slug': ads1.slug,
            'search_rank': mock.ANY,
            'short_description': ads1.short_description,
            'published': True,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ads1.type,
            'has_access': False,
        },
    ]


def test_datasets_and_visualisations_doesnt_return_duplicate_results(staff_client,):
    normal_user = get_user_model().objects.create(
        username='bob.user@test.com', is_staff=False, is_superuser=False
    )
    staff_user = get_user_model().objects.create(
        username='bob.staff@test.com', is_staff=True, is_superuser=True
    )

    users = [factories.UserFactory.create() for _ in range(3)]
    source_tags = [factories.SourceTagFactory.create() for _ in range(5)]

    master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER.value,
        name='A master',
        user_access_type='REQUIRES_AUTHENTICATION',
    )
    master2 = factories.DataSetFactory.create(
        published=False,
        type=DataSetType.MASTER.value,
        name='A master',
        user_access_type='REQUIRES_AUTHORIZATION',
    )
    datacut = factories.DataSetFactory.create(
        published=False,
        type=DataSetType.DATACUT.value,
        name='A datacut',
        user_access_type='REQUIRES_AUTHENTICATION',
    )
    datacut2 = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT.value,
        name='A datacut',
        user_access_type='REQUIRES_AUTHORIZATION',
    )
    factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    visualisation = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='A visualisation'
    )

    for user in users + [normal_user, staff_user]:
        factories.DataSetUserPermissionFactory.create(dataset=master, user=user)
        master.source_tags.set(random.sample(source_tags, 3))
        factories.DataSetUserPermissionFactory.create(dataset=master2, user=user)
        master2.source_tags.set(random.sample(source_tags, 3))

        factories.DataSetUserPermissionFactory.create(dataset=datacut, user=user)
        datacut.source_tags.set(random.sample(source_tags, 3))
        factories.DataSetUserPermissionFactory.create(dataset=datacut2, user=user)
        datacut2.source_tags.set(random.sample(source_tags, 3))

        factories.VisualisationUserPermissionFactory.create(
            visualisation=visualisation, user=user
        )

    for u in [normal_user, staff_user]:
        datasets = get_datasets_data_for_user_matching_query(
            DataSet.objects.live(), query='', use={}, user=u
        )
        assert len(datasets) == len(set(dataset['id'] for dataset in datasets))

        references = get_datasets_data_for_user_matching_query(
            ReferenceDataset.objects.live(), '', {}, user=u
        )
        assert len(references) == len(set(reference['id'] for reference in references))

        visualisations = get_visualisations_data_for_user_matching_query(
            VisualisationCatalogueItem.objects, query='', user=u
        )
        assert len(visualisations) == len(
            set(visualisation['id'] for visualisation in visualisations)
        )


def test_finding_datasets_doesnt_query_database_excessively(
    client, django_assert_num_queries
):
    """
    This test generates a random number of master datasets, datacuts, reference datasets and visualisations, and asserts
    that the number of queries executed by the search page remains stable. This is potentially a flaky test, given
    that the inputs are indeterminate, but it would at least highlight at some point that we have an unknown issue.
    """
    source_tags = [factories.SourceTagFactory() for _ in range(10)]

    masters = [
        factories.DataSetFactory(
            type=DataSetType.MASTER.value,
            published=True,
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        for _ in range(random.randint(10, 50))
    ]
    for master in masters:
        master.source_tags.set(random.sample(source_tags, random.randint(1, 3)))

    datacuts = [
        factories.DataSetFactory(
            type=DataSetType.DATACUT.value,
            published=True,
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        for _ in range(random.randint(10, 50))
    ]
    for datacut in datacuts:
        datacut.source_tags.set(random.sample(source_tags, 1))

    references = [factories.ReferenceDatasetFactory(published=True,) for _ in range(10)]
    for reference in references:
        reference.source_tags.set(random.sample(source_tags, random.randint(1, 3)))

    visualisations = [
        factories.VisualisationCatalogueItemFactory.create(published=True,)
        for _ in range(random.randint(10, 50))
    ]

    for visualisation in visualisations:
        factories.DataSetApplicationTemplatePermissionFactory(
            application_template=visualisation.visualisation_template,
            dataset=random.choice(masters),
        )

    # Log into site (triggers the queries related to setting up the user).
    client.get(reverse('root'))

    with django_assert_num_queries(10, exact=False):
        response = client.get(reverse('datasets:find_datasets'), follow=True)
        assert response.status_code == 200

    with django_assert_num_queries(10, exact=False):
        response = client.get(reverse('datasets:find_datasets'), {"q": "potato"})
        assert response.status_code == 200

    with django_assert_num_queries(11, exact=False):
        response = client.get(
            reverse('datasets:find_datasets'),
            {
                "source": [
                    str(tag.id)
                    for tag in random.sample(source_tags, random.randint(1, 5))
                ]
            },
        )
        assert response.status_code == 200

    with django_assert_num_queries(10, exact=False):
        response = client.get(
            reverse('datasets:find_datasets'),
            {"purpose": str(DataSetType.MASTER.value)},
        )
        assert response.status_code == 200

    with django_assert_num_queries(10, exact=False):
        response = client.get(reverse('datasets:find_datasets'), {"access": "yes"},)
        assert response.status_code == 200


@pytest.mark.django_db
def test_find_datasets_filters_by_access():
    user = factories.UserFactory.create(is_superuser=False)
    user2 = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    public_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER.value,
        name='Master - public',
        user_access_type='REQUIRES_AUTHENTICATION',
    )
    access_granted_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER.value,
        name='Master - access granted',
        user_access_type='REQUIRES_AUTHORIZATION',
    )

    factories.DataSetUserPermissionFactory.create(
        user=user, dataset=access_granted_master
    )
    factories.DataSetUserPermissionFactory.create(
        user=user2, dataset=access_granted_master
    )
    factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER.value,
        name='Master - access not granted',
        user_access_type='REQUIRES_AUTHORIZATION',
    )

    access_not_granted_datacut = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.DATACUT.value,
        name='Datacut - access not granted',
        user_access_type='REQUIRES_AUTHORIZATION',
    )
    factories.DataSetUserPermissionFactory.create(
        user=user2, dataset=access_not_granted_datacut
    )

    public_reference = factories.ReferenceDatasetFactory.create(
        published=True, name='Reference - public'
    )

    access_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True, name='Visualisation', user_access_type='REQUIRES_AUTHORIZATION'
    )
    factories.VisualisationUserPermissionFactory(user=user, visualisation=access_vis)
    factories.VisualisationUserPermissionFactory(user=user2, visualisation=access_vis)

    no_access_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name='Visualisation - hidden',
        user_access_type='REQUIRES_AUTHORIZATION',
    )
    factories.VisualisationUserPermissionFactory(
        user=user2, visualisation=no_access_vis
    )

    public_vis = factories.VisualisationCatalogueItemFactory.create(
        published=True,
        name='Visualisation - public',
        user_access_type='REQUIRES_AUTHENTICATION',
    )

    response = client.get(reverse('datasets:find_datasets'), {"access": "yes"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': access_granted_master.id,
            'name': access_granted_master.name,
            'slug': access_granted_master.slug,
            'search_rank': mock.ANY,
            'short_description': access_granted_master.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': access_granted_master.type,
            'published': True,
            'has_access': True,
        },
        {
            'id': public_master.id,
            'name': public_master.name,
            'slug': public_master.slug,
            'search_rank': mock.ANY,
            'short_description': public_master.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': public_master.type,
            'published': True,
            'has_access': True,
        },
        {
            'id': public_reference.uuid,
            'name': public_reference.name,
            'slug': public_reference.slug,
            'search_rank': mock.ANY,
            'short_description': public_reference.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
        {
            'id': access_vis.id,
            'name': access_vis.name,
            'slug': access_vis.slug,
            'search_rank': mock.ANY,
            'short_description': access_vis.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'published': True,
            'has_access': True,
        },
        {
            'id': public_vis.id,
            'name': public_vis.name,
            'slug': public_vis.slug,
            'search_rank': mock.ANY,
            'short_description': public_vis.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'published': True,
            'has_access': True,
        },
    ]


@pytest.mark.django_db
def test_find_datasets_filters_by_access_and_use_only_returns_the_dataset_once():
    """Meant to prevent a regression where the combination of these two filters would return datasets multiple times
    based on the number of users with permissions to see that dataset, but the dataset didn't actually require any
    permission to use."""
    user = factories.UserFactory.create(is_superuser=False)
    user2 = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    access_granted_master = factories.DataSetFactory.create(
        published=True,
        type=DataSetType.MASTER.value,
        name='Master - access redundantly granted',
        user_access_type='REQUIRES_AUTHENTICATION',
    )
    factories.DataSetUserPermissionFactory.create(
        user=user, dataset=access_granted_master
    )
    factories.DataSetUserPermissionFactory.create(
        user=user2, dataset=access_granted_master
    )

    response = client.get(
        reverse('datasets:find_datasets'),
        {"access": "yes", "use": str(DataSetType.MASTER.value)},
    )

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': access_granted_master.id,
            'name': access_granted_master.name,
            'slug': access_granted_master.slug,
            'search_rank': mock.ANY,
            'short_description': access_granted_master.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': access_granted_master.type,
            'published': True,
            'has_access': True,
        }
    ]


@pytest.mark.parametrize(
    'permissions, result_dataset_names',
    (
        (['manage_unpublished_master_datasets'], {"Master dataset"}),
        (['manage_unpublished_datacut_datasets'], {"Datacut dataset"}),
        (['manage_unpublished_reference_datasets'], {"Reference dataset"}),
        (['manage_unpublished_visualisations'], {"Visualisation"}),
        (
            [
                'manage_unpublished_master_datasets',
                'manage_unpublished_datacut_datasets',
            ],
            {"Master dataset", "Datacut dataset"},
        ),
        (
            [
                'manage_unpublished_master_datasets',
                'manage_unpublished_reference_datasets',
            ],
            {"Master dataset", "Reference dataset"},
        ),
        (
            [
                'manage_unpublished_datacut_datasets',
                'manage_unpublished_reference_datasets',
            ],
            {"Datacut dataset", "Reference dataset"},
        ),
        (
            [
                'manage_unpublished_master_datasets',
                'manage_unpublished_datacut_datasets',
                'manage_unpublished_reference_datasets',
            ],
            {"Master dataset", "Datacut dataset", "Reference dataset"},
        ),
        (
            ['manage_unpublished_master_datasets', 'manage_unpublished_visualisations'],
            {"Master dataset", "Visualisation"},
        ),
        (
            [
                'manage_unpublished_master_datasets',
                'manage_unpublished_reference_datasets',
                'manage_unpublished_visualisations',
            ],
            {"Master dataset", "Reference dataset", "Visualisation"},
        ),
    ),
)
@pytest.mark.django_db
def test_find_datasets_includes_unpublished_results_based_on_permissions(
    permissions, result_dataset_names
):
    user = get_user_model().objects.create(is_staff=True)
    perms = Permission.objects.filter(codename__in=permissions).all()
    user.user_permissions.add(*perms)
    user.save()

    client = Client(**get_http_sso_data(user))

    factories.DataSetFactory.create(
        published=False, type=DataSetType.MASTER.value, name='Master dataset'
    )
    factories.DataSetFactory.create(
        published=False, type=DataSetType.DATACUT.value, name='Datacut dataset'
    )
    factories.ReferenceDatasetFactory.create(published=False, name='Reference dataset')

    factories.VisualisationCatalogueItemFactory.create(
        published=False, name='Visualisation'
    )

    response = client.get(reverse('datasets:find_datasets'))

    assert response.status_code == 200
    assert {
        dataset['name'] for dataset in response.context["datasets"]
    } == result_dataset_names


def test_request_access_success_content(client):
    ds = factories.DataSetFactory.create(published=True, type=1, name='A dataset')

    response = client.get(
        reverse('datasets:request_access_success', kwargs={"dataset_uuid": ds.id}),
        {"ticket": "test-ticket-id"},
    )

    assert (
        'Your request has been received. It will normally be completed within 5 working days.'
        in response.content.decode(response.charset)
    )


@pytest.mark.parametrize(
    "source_urls, show_warning",
    (
        (["s3://some-bucket/some-object"], False),
        (["s3://some-bucket/some-object", "s3://some-bucket/some-other-object"], False),
        (["http://some.data.com/download.csv"], True),
        (["s3://some-bucket/some-object", "http://some.data.com/download.csv"], True),
    ),
)
@pytest.mark.django_db
def test_dataset_shows_external_link_warning(source_urls, show_warning):
    ds = factories.DataSetFactory.create(published=True)
    user = get_user_model().objects.create()
    factories.DataSetUserPermissionFactory.create(user=user, dataset=ds)

    for source_url in source_urls:
        factories.SourceLinkFactory.create(dataset=ds, url=source_url)

    client = Client(**get_http_sso_data(user))
    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert (
        "This data set is hosted by an external source."
        in response.content.decode(response.charset)
    ) is show_warning


@pytest.mark.django_db
def test_dataset_shows_code_snippets_to_tool_user(metadata_db):
    ds = factories.DataSetFactory.create(type=DataSetType.MASTER.value, published=True)
    user = get_user_model().objects.create(is_superuser=False)
    factories.DataSetUserPermissionFactory.create(user=user, dataset=ds)
    factories.SourceTableFactory.create(
        dataset=ds,
        schema="public",
        table="MY_LOVELY_TABLE",
        database=factories.DatabaseFactory(memorable_name='my_database'),
    )

    client = Client(**get_http_sso_data(user))
    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert (
        """SELECT * FROM &quot;public&quot;.&quot;MY_LOVELY_TABLE&quot; LIMIT 50"""
        not in response.content.decode(response.charset)
    )

    user.is_superuser = True
    user.save()

    client = Client(**get_http_sso_data(user))
    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert (
        """SELECT * FROM &quot;public&quot;.&quot;MY_LOVELY_TABLE&quot; LIMIT 50"""
        in response.content.decode(response.charset)
    )


@pytest.mark.django_db(transaction=True)
def test_launch_master_dataset_in_data_explorer(metadata_db):
    ds = factories.DataSetFactory.create(type=DataSetType.MASTER.value, published=True)
    user = get_user_model().objects.create(is_superuser=True)
    factories.DataSetUserPermissionFactory.create(user=user, dataset=ds)
    factories.SourceTableFactory.create(
        dataset=ds,
        schema="public",
        table="MY_LOVELY_TABLE",
        database=factories.DatabaseFactory(memorable_name='my_database'),
    )
    flag = Flag.objects.create(
        name=DATA_EXPLORER_FLAG, everyone=False, superusers=False
    )
    expected_sql = quote_plus("""SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50""")

    client = Client(**get_http_sso_data(user))
    response = client.get(ds.get_absolute_url())
    doc = html.fromstring(response.content.decode(response.charset))

    assert response.status_code == 200
    assert doc.xpath("//a[normalize-space(text()) = 'Open in Data Explorer']") == []

    flag.everyone = True
    flag.save()

    client = Client(**get_http_sso_data(user))
    response = client.get(ds.get_absolute_url())
    doc = html.fromstring(response.content.decode(response.charset))

    assert response.status_code == 200
    assert (
        doc.xpath("//a[normalize-space(text()) = 'Open in Data Explorer']/@href")[0]
        == f'/data-explorer/?sql={expected_sql}'
    )


class TestVisualisationsDetailView:
    def test_get_published_authenticated_visualisation(self, client):
        vis = VisualisationCatalogueItemFactory()

        response = client.get(vis.get_absolute_url())

        assert response.status_code == 200
        assert vis.name in response.content.decode(response.charset)

    @pytest.mark.parametrize('has_access', (True, False))
    @pytest.mark.django_db
    def test_unauthorised_visualisation(self, has_access):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type='REQUIRES_AUTHORIZATION'
        )

        if has_access:
            VisualisationUserPermissionFactory.create(visualisation=vis, user=user)

        client = Client(**get_http_sso_data(user))
        response = client.get(vis.get_absolute_url())

        assert response.status_code == 200
        assert vis.name in response.content.decode(response.charset)
        assert (
            "You do not have permission to access this data visualisation."
            in response.content.decode(response.charset)
        ) is not has_access

    def test_shows_links_to_visualisations(self, client):
        vis = VisualisationCatalogueItemFactory.create(
            visualisation_template__host_basename='visualisation'
        )
        link1 = VisualisationLinkFactory.create(
            visualisation_type='DATASTUDIO',
            visualisation_catalogue_item=vis,
            name='Visualisation datastudio',
            identifier='https://www.data.studio.test',
        )
        link2 = VisualisationLinkFactory.create(
            visualisation_type='QUICKSIGHT',
            visualisation_catalogue_item=vis,
            name='Visualisation quicksight',
            identifier='5d75e131-20f4-48f8-b0eb-f4ebf36434f4',
        )

        response = client.get(vis.get_absolute_url())
        body = response.content.decode(response.charset)

        assert response.status_code == 200
        assert '//visualisation.dataworkspace.test:8000/' in body
        assert f'/visualisations/link/{link1.id}' in body
        assert f'/visualisations/link/{link2.id}' in body


class TestVisualisationLinkView:
    @pytest.mark.django_db
    def test_quicksight_link(self, mocker):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        link = VisualisationLinkFactory.create(
            visualisation_type='QUICKSIGHT',
            identifier='5d75e131-20f4-48f8-b0eb-f4ebf36434f4',
            visualisation_catalogue_item=vis,
        )

        quicksight = mocker.patch(
            'dataworkspace.apps.applications.views.get_quicksight_dashboard_name_url'
        )
        quicksight.return_value = (
            'my-dashboard',
            'https://my.dashboard.quicksight.amazonaws.com',
        )
        eventlog_count = EventLog.objects.count()

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())

        assert response.status_code == 200
        assert (
            'https://my.dashboard.quicksight.amazonaws.com'
            in response.content.decode(response.charset)
        )
        assert (
            'frame-src https://eu-west-2.quicksight.aws.amazon.com'
            in response['content-security-policy']
        )
        assert (
            'frame-ancestors dataworkspace.test:8000 https://authorized-embedder.com'
            in response['content-security-policy']
        )
        assert EventLog.objects.count() == eventlog_count + 1
        assert (
            list(EventLog.objects.all())[-1].event_type
            == EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION
        )

    @pytest.mark.django_db
    def test_datastudio_link(self):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        link = VisualisationLinkFactory.create(
            visualisation_type='DATASTUDIO',
            identifier='https://www.data.studio',
            visualisation_catalogue_item=vis,
        )
        eventlog_count = EventLog.objects.count()

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())

        assert response.status_code == 302
        assert response['location'] == 'https://www.data.studio'
        assert EventLog.objects.count() == eventlog_count + 1
        assert (
            list(EventLog.objects.all())[-1].event_type
            == EventLog.TYPE_VIEW_DATASTUDIO_VISUALISATION
        )

    @pytest.mark.django_db
    def test_user_needs_access_via_catalogue_item(self, mocker):
        user = UserFactory.create()
        vis = VisualisationCatalogueItemFactory.create(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        link = VisualisationLinkFactory.create(
            visualisation_type='QUICKSIGHT',
            identifier=str(uuid4()),
            visualisation_catalogue_item=vis,
        )
        quicksight = mocker.patch(
            'dataworkspace.apps.applications.views.get_quicksight_dashboard_name_url'
        )
        quicksight.return_value = (
            'my-dashboard',
            'https://my.dashboard.quicksight.amazonaws.com',
        )

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())
        assert response.status_code == 403

        VisualisationUserPermissionFactory.create(visualisation=vis, user=user)

        response = client.get(link.get_absolute_url())
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_invalid_link_404s(self):
        user = UserFactory.create()

        client = Client(**get_http_sso_data(user))
        response = client.get(
            reverse(
                'visualisations:link',
                kwargs={"link_id": "2af5890a-bbcc-4e7d-8b2d-2a63139b3e4f"},
            )
        )
        assert response.status_code == 404


def test_find_datasets_search_by_source_name(client):
    source = factories.SourceTagFactory(name='source1')
    source_2 = factories.SourceTagFactory(name='source2')
    ds1 = factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    ds1.source_tags.set([source, source_2])

    ds2 = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    ds2.source_tags.set([factories.SourceTagFactory(name='source3')])

    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    rds.source_tags.set([source])

    response = client.get(reverse('datasets:find_datasets'), {"q": "source1"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds1.id,
            'name': ds1.name,
            'slug': ds1.slug,
            'search_rank': 0.243171,
            'short_description': ds1.short_description,
            'published_at': mock.ANY,
            'source_tag_names': [source.name, source_2.name],
            'source_tag_ids': MatchUnorderedMembers([source.id, source_2.id]),
            'purpose': ds1.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': 0.243171,
            'short_description': rds.short_description,
            'published_at': mock.ANY,
            'source_tag_names': [source.name],
            'source_tag_ids': [source.id],
            'purpose': DataSetType.REFERENCE.value,
            'published': True,
            'has_access': True,
        },
    ]


def test_find_datasets_name_weighting(client):
    ds1 = factories.DataSetFactory.create(
        published=True, type=1, name='A dataset with a keyword'
    )
    ds2 = factories.DataSetFactory.create(
        published=True,
        type=2,
        name='A dataset',
        short_description='Keyword appears in short description',
    )
    factories.DataSetFactory.create(
        published=True, type=1, name='Does not appear in search'
    )
    ds4 = factories.DataSetFactory.create(
        published=True,
        type=2,
        name='Another dataset but the keyword appears twice, keyword.',
    )

    response = client.get(reverse('datasets:find_datasets'), {"q": "keyword"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds4.id,
            'name': ds4.name,
            'slug': ds4.slug,
            'search_rank': 0.759909,
            'short_description': ds4.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds4.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': ds1.id,
            'name': ds1.name,
            'slug': ds1.slug,
            'search_rank': 0.607927,
            'short_description': ds1.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds1.type,
            'published': True,
            'has_access': False,
        },
        {
            'id': ds2.id,
            'name': ds2.name,
            'slug': ds2.slug,
            'search_rank': 0.243171,
            'short_description': ds2.short_description,
            'published_at': mock.ANY,
            'source_tag_names': mock.ANY,
            'source_tag_ids': mock.ANY,
            'purpose': ds2.type,
            'published': True,
            'has_access': False,
        },
    ]


def test_find_datasets_matches_both_source_and_name(client):
    source_1 = factories.SourceTagFactory(name='source1')
    source_2 = factories.SourceTagFactory(name='source2')

    ds1 = factories.DataSetFactory.create(
        published=True, type=1, name='A dataset from source1'
    )
    ds1.source_tags.set([source_1, source_2])

    response = client.get(reverse('datasets:find_datasets'), {"q": "source1"})

    assert response.status_code == 200
    assert len(list(response.context["datasets"])) == 1
    assert list(response.context["datasets"]) == [
        {
            'id': ds1.id,
            'name': ds1.name,
            'slug': ds1.slug,
            'search_rank': mock.ANY,
            'short_description': ds1.short_description,
            'published_at': mock.ANY,
            'source_tag_names': [source_1.name, source_2.name],
            'source_tag_ids': MatchUnorderedMembers([source_1.id, source_2.id]),
            'purpose': ds1.type,
            'published': True,
            'has_access': False,
        }
    ]


class TestCustomQueryRelatedDataView:
    def _get_dsn(self):
        return database_dsn(settings.DATABASES_DATA['my_database'])

    def _get_database(self):
        return factories.DatabaseFactory(memorable_name='my_database')

    def _setup_datacut_with_masters(self, sql, master_count=1, published=True):
        masters = []
        for _ in range(master_count):
            master = factories.DataSetFactory.create(
                published=published,
                type=DataSetType.MASTER.value,
                name='A master 1',
                user_access_type='REQUIRES_AUTHENTICATION',
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
            type=DataSetType.DATACUT.value,
            name='A datacut',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=datacut, database=self._get_database(), query=sql,
        )
        factories.CustomDatasetQueryTableFactory(
            query=query, schema='public', table='test_dataset'
        )
        return datacut, masters

    def _setup_new_table(self):
        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS custom_query_test (
                    id INT,
                    name VARCHAR(255),
                    date DATE
                );
                TRUNCATE TABLE custom_query_test;
                INSERT INTO custom_query_test VALUES(1, 'the first record', NULL);
                INSERT INTO custom_query_test VALUES(2, 'the second record', '2019-01-01');
                INSERT INTO custom_query_test VALUES(3, 'the last record', NULL);
                '''
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
    @pytest.mark.django_db
    def test_related_dataset_dataset(self, request_client, master_count, status):
        datacut, masters = self._setup_datacut_with_masters(
            'SELECT * FROM test_dataset order by id desc limit 10',
            master_count=master_count,
            published=True,
        )
        url = reverse('datasets:dataset_detail', args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_masters"]) == master_count
        for master in masters:
            related_master = [
                item
                for item in response.context["related_masters"]
                if item.id == master.id
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
    @pytest.mark.django_db
    def test_related_dataset_hide_unpublished_master(
        self, request_client, master_count, status
    ):
        published_master = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER.value,
            name='Published master',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        factories.SourceTableFactory.create(
            dataset=published_master,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )
        unpublished_master = factories.DataSetFactory.create(
            published=False,
            type=DataSetType.MASTER.value,
            name='Unpublished master',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        factories.SourceTableFactory.create(
            dataset=unpublished_master,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )

        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT.value,
            name='A datacut',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query='SELECT * FROM test_dataset order by id desc limit 10',
        )
        factories.CustomDatasetQueryTableFactory(
            query=query, schema='public', table='test_dataset'
        )

        url = reverse('datasets:dataset_detail', args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_masters"]) == 1

    @pytest.mark.parametrize(
        "request_client, status",
        (("sme_client", 200), ("staff_client", 200),),
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_related_dataset_does_not_duplicate_masters(self, request_client, status):
        self._setup_new_table()
        master1 = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.MASTER.value,
            name='A master 1',
            user_access_type='REQUIRES_AUTHENTICATION',
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
            type=DataSetType.MASTER.value,
            name='A master 1',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        factories.SourceTableFactory.create(
            dataset=master2,
            schema="public",
            table="test_dataset",
            database=self._get_database(),
        )

        datacut = factories.DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT.value,
            name='A datacut',
            user_access_type='REQUIRES_AUTHENTICATION',
        )
        query1 = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query='SELECT * FROM test_dataset order by id desc limit 10',
        )
        factories.CustomDatasetQueryTableFactory(
            query=query1, schema='public', table='test_dataset'
        )
        query2 = factories.CustomDatasetQueryFactory(
            dataset=datacut,
            database=self._get_database(),
            query='SELECT * FROM custom_query_test order by id desc limit 10',
        )
        factories.CustomDatasetQueryTableFactory(
            query=query2, schema='public', table='custom_query_test'
        )

        url = reverse('datasets:dataset_detail', args=(datacut.id,))
        response = request_client.get(url)
        assert response.status_code == status
        assert len(response.context["related_masters"]) == 2
