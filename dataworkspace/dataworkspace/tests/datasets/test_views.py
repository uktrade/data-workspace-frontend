import mock
import pytest
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from django.test import Client

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data
from dataworkspace.tests.factories import (
    VisualisationCatalogueItemFactory,
    UserFactory,
    ApplicationTemplateUserPermissionFactory,
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

    ds = factories.DataSetFactory.create(published=True)

    response = client.post(
        reverse('datasets:request_access', kwargs={'dataset_uuid': ds.id}),
        data={"email": "user@example.com", "goal": "My goal"},
        follow=True,
    )

    assert response.status_code == 200

    create_zendesk_ticket.assert_called_once_with(
        "user@example.com", mock.ANY, "My goal", mock.ANY, ds.name, mock.ANY, None, None
    )


def test_request_visualisation_access(client, mocker):
    create_zendesk_ticket = mocker.patch(
        'dataworkspace.apps.datasets.views.create_support_request'
    )

    ds = factories.VisualisationCatalogueItemFactory.create(published=True)

    response = client.post(
        reverse(
            'datasets:request_visualisation_access', kwargs={'dataset_uuid': ds.id}
        ),
        data={},
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

    response = client.get(reverse('datasets:find_datasets'), {"q": "search"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
        },
    ]

    assert "If you haven’t found what you’re looking for" in response.content.decode(
        response.charset
    )


def test_find_datasets_filters_by_query(client):
    factories.DataSetFactory.create(published=True, name='A dataset')
    factories.ReferenceDatasetFactory.create(published=True, name='A reference dataset')

    ds = factories.DataSetFactory.create(published=True, name='A new dataset')
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
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
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
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
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
        },
    ]


def test_find_datasets_filters_by_source(client):
    source = factories.SourceTagFactory()
    _ds = factories.DataSetFactory.create(published=True, type=1, name='A dataset')
    _ds.source_tags.set([factories.SourceTagFactory()])

    ds = factories.DataSetFactory.create(published=True, type=2, name='A new dataset')
    ds.source_tags.set([source, factories.SourceTagFactory()])

    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A new reference dataset'
    )
    rds.source_tags.set([source])

    response = client.get(reverse('datasets:find_datasets'), {"source": [source.id]})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': ds.id,
            'name': ds.name,
            'slug': ds.slug,
            'search_rank': mock.ANY,
            'short_description': ds.short_description,
        },
        {
            'id': rds.uuid,
            'name': rds.name,
            'slug': rds.slug,
            'search_rank': mock.ANY,
            'short_description': rds.short_description,
        },
    ]


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

    response = client.get(reverse('datasets:find_datasets'), {"access": "yes"})

    assert response.status_code == 200
    assert list(response.context["datasets"]) == [
        {
            'id': access_granted_master.id,
            'name': access_granted_master.name,
            'slug': access_granted_master.slug,
            'search_rank': mock.ANY,
            'short_description': access_granted_master.short_description,
        },
        {
            'id': public_master.id,
            'name': public_master.name,
            'slug': public_master.slug,
            'search_rank': mock.ANY,
            'short_description': public_master.short_description,
        },
        {
            'id': public_reference.uuid,
            'name': public_reference.name,
            'slug': public_reference.slug,
            'search_rank': mock.ANY,
            'short_description': public_reference.short_description,
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
        }
    ]


@pytest.mark.parametrize(
    'permissions, result_dataset_names',
    (
        (['manage_unpublished_master_datasets'], {"Master dataset"}),
        (['manage_unpublished_datacut_datasets'], {"Datacut dataset"}),
        (['manage_unpublished_reference_datasets'], {"Reference dataset"}),
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
    ),
)
@pytest.mark.django_db
def test_find_datasets_includes_unpublished_results_based_on_permissions(
    permissions, result_dataset_names
):
    user = User.objects.create(is_staff=True)
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
    user = User.objects.create()
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
    user = User.objects.create(is_superuser=False)
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
            visualisation_template__user_access_type='REQUIRES_AUTHORIZATION'
        )

        if has_access:
            ApplicationTemplateUserPermissionFactory.create(
                application_template=vis.visualisation_template, user=user
            )

        client = Client(**get_http_sso_data(user))
        response = client.get(vis.get_absolute_url())

        assert response.status_code == 200
        assert vis.name in response.content.decode(response.charset)
        assert (
            "You do not have permission to access this data visualisation."
            in response.content.decode(response.charset)
        ) is not has_access

    def test_shows_link_to_visualisation(self, client):
        vis = VisualisationCatalogueItemFactory(
            visualisation_template__host_basename='visualisation'
        )

        response = client.get(vis.get_absolute_url())

        assert response.status_code == 200
        assert (
            'http://visualisation.dataworkspace.test:8000/'
            in response.content.decode(response.charset)
        )
