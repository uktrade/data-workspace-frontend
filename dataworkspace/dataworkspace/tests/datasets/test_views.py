import random
from uuid import uuid4

import mock
import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import Client

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data, MatchUnorderedMembers
from dataworkspace.tests.factories import (
    VisualisationCatalogueItemFactory,
    UserFactory,
    VisualisationUserPermissionFactory,
    VisualisationLinkFactory,
)


@pytest.mark.parametrize(
    'eligibility_criteria,view_name',
    [
        ([], 'datasets:request_access'),
        (['Criteria 1', 'Criteria 2'], 'datasets:eligibility_criteria'),
    ],
)
def test_dataset_has_request_access_link(client, eligibility_criteria, view_name):
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
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
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
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
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
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
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
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
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
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
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
            'source_tag_ids': mock.ANY,
            'purpose': ds.type,
            'has_access': False,
        },
        {
            'id': vis.id,
            'name': vis.name,
            'slug': vis.slug,
            'search_rank': mock.ANY,
            'short_description': vis.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
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
            'source_tag_ids': MatchUnorderedMembers([source.id, source_2.id]),
            'purpose': ds.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': 0.0,
            'short_description': rds.short_description,
            'source_tag_ids': [source.id],
            'purpose': DataSetType.REFERENCE.value,
            'has_access': True,
        },
    ]

    assert len(list(response.context["form"].fields['source'].choices)) == 3


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
            'source_tag_ids': mock.ANY,
            'purpose': access_granted_master.type,
            'has_access': True,
        },
        {
            'id': public_master.id,
            'name': public_master.name,
            'slug': public_master.slug,
            'search_rank': mock.ANY,
            'short_description': public_master.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': public_master.type,
            'has_access': True,
        },
        {
            'id': public_reference.uuid,
            'name': public_reference.name,
            'slug': public_reference.slug,
            'search_rank': mock.ANY,
            'short_description': public_reference.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.REFERENCE.value,
            'has_access': True,
        },
        {
            'id': access_vis.id,
            'name': access_vis.name,
            'slug': access_vis.slug,
            'search_rank': mock.ANY,
            'short_description': access_vis.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
            'has_access': True,
        },
        {
            'id': public_vis.id,
            'name': public_vis.name,
            'slug': public_vis.slug,
            'search_rank': mock.ANY,
            'short_description': public_vis.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': DataSetType.VISUALISATION.value,
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
            'source_tag_ids': mock.ANY,
            'purpose': access_granted_master.type,
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
def test_dataset_shows_code_snippets_to_tool_user():
    ds = factories.DataSetFactory.create(type=DataSetType.MASTER.value, published=True)
    user = get_user_model().objects.create(is_superuser=False)
    factories.DataSetUserPermissionFactory.create(user=user, dataset=ds)
    factories.SourceTableFactory.create(
        dataset=ds, schema="public", table="MY_LOVELY_TABLE"
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

        client = Client(**get_http_sso_data(user))
        response = client.get(link.get_absolute_url())

        assert response.status_code == 302
        assert response['location'] == 'https://www.data.studio'

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

    ds1 = factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    ds1.source_tags.set([source, factories.SourceTagFactory()])

    ds2 = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    ds2.source_tags.set([factories.SourceTagFactory(name='source2')])

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
            'source_tag_ids': [source.id],
            'purpose': ds1.type,
            'has_access': False,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': 0.243171,
            'short_description': rds.short_description,
            'source_tag_ids': [source.id],
            'purpose': DataSetType.REFERENCE.value,
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
            'source_tag_ids': mock.ANY,
            'purpose': ds4.type,
            'has_access': False,
        },
        {
            'id': ds1.id,
            'name': ds1.name,
            'slug': ds1.slug,
            'search_rank': 0.607927,
            'short_description': ds1.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': ds1.type,
            'has_access': False,
        },
        {
            'id': ds2.id,
            'name': ds2.name,
            'slug': ds2.slug,
            'search_rank': 0.243171,
            'short_description': ds2.short_description,
            'source_tag_ids': mock.ANY,
            'purpose': ds2.type,
            'has_access': False,
        },
    ]
