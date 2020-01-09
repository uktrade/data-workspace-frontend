import mock
import pytest
from django.urls import reverse
from waffle.testutils import override_flag

from dataworkspace.tests import factories


@pytest.mark.parametrize(
    'eligibility_criteria,view_name',
    [
        ([], 'datasets:request_access'),
        (['Criteria 1', 'Criteria 2'], 'datasets:eligibility_criteria'),
    ],
)
def test_dataset_has_request_access_link(client, eligibility_criteria, view_name):
    group = factories.DataGroupingFactory.create()
    ds = factories.DataSetFactory.create(
        grouping=group, eligibility_criteria=eligibility_criteria, published=True
    )

    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    request_access_url = reverse(view_name, args=[group.slug, ds.slug])

    assert response.status_code == 200
    assert request_access_url in str(response.content)


def test_eligibility_criteria_list(client):
    group = factories.DataGroupingFactory.create()
    ds = factories.DataSetFactory.create(
        grouping=group,
        eligibility_criteria=['Criteria 1', 'Criteria 2'],
        published=True,
    )

    response = client.get(
        reverse(
            'datasets:eligibility_criteria',
            kwargs={'group_slug': group.slug, 'set_slug': ds.slug},
        )
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
    group = factories.DataGroupingFactory.create()
    ds = factories.DataSetFactory.create(
        grouping=group,
        eligibility_criteria=['Criteria 1', 'Criteria 3'],
        published=True,
    )

    response = client.post(
        reverse(
            'datasets:eligibility_criteria',
            kwargs={'group_slug': group.slug, 'set_slug': ds.slug},
        ),
        data={"meet_criteria": meet_criteria},
        follow=True,
    )

    test_case.assertRedirects(
        response,
        reverse(redirect_view, kwargs={'group_slug': group.slug, 'set_slug': ds.slug}),
    )


def test_request_access_form(client, mocker):
    create_zendesk_ticket = mocker.patch(
        'dataworkspace.apps.datasets.views.create_zendesk_ticket'
    )

    group = factories.DataGroupingFactory.create()
    ds = factories.DataSetFactory.create(grouping=group, published=True)

    response = client.post(
        reverse(
            'datasets:request_access',
            kwargs={'group_slug': group.slug, 'set_slug': ds.slug},
        ),
        data={
            "email": "user@example.com",
            "goal": "My goal",
            "justification": "My justification",
        },
        follow=True,
    )

    assert response.status_code == 200

    create_zendesk_ticket.assert_called_once_with(
        "user@example.com",
        mock.ANY,
        "My goal",
        "My justification",
        mock.ANY,
        f"{group.name} > {ds.name}",
        mock.ANY,
        None,
        None,
    )


def test_old_dataset_url_redirects_to_new_url(client):
    ds = factories.DataSetFactory.create(published=True)
    response = client.get(
        reverse(
            'catalogue:dataset_fullpath',
            kwargs={'group_slug': ds.grouping.slug, 'set_slug': ds.slug},
        )
    )
    assert response.status_code == 302
    assert response['Location'] == ds.get_absolute_url()


def test_old_reference_dataset_url_redirects_to_new_url(client):
    group = factories.DataGroupingFactory.create()
    rds = factories.ReferenceDatasetFactory.create(
        group=group, table_name='test_detail_view'
    )
    response = client.get(
        reverse(
            'catalogue:reference_dataset',
            kwargs={'group_slug': group.slug, 'reference_slug': rds.slug},
        )
    )
    assert response.status_code == 302
    assert response['Location'] == rds.get_absolute_url()


@override_flag('datasets-search', active=True)
def test_find_datasets_combines_results(client):
    ds = factories.DataSetFactory.create(published=True, name='A dataset')
    rds = factories.ReferenceDatasetFactory.create(
        published=True, name='A reference dataset'
    )

    response = client.get(reverse('datasets:find_datasets'))

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


@override_flag('datasets-search', active=True)
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


@override_flag('datasets-search', active=True)
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


@override_flag('datasets-search', active=True)
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
