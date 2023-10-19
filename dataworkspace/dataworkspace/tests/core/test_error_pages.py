import mock
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data
from dataworkspace.tests.explorer.factories import QueryLogFactory


@pytest.mark.parametrize(
    "url_name,dataset_factories",
    (
        (
            "datasets:dataset_detail",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
                factories.ReferenceDatasetFactory,
                factories.VisualisationCatalogueItemFactory,
            ),
        ),
        (
            "datasets:dataset_detail",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
                factories.ReferenceDatasetFactory,
                factories.VisualisationCatalogueItemFactory,
            ),
        ),
        (
            "datasets:eligibility_criteria",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
                factories.ReferenceDatasetFactory,
                factories.VisualisationCatalogueItemFactory,
            ),
        ),
        (
            "datasets:eligibility_criteria_not_met",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
                factories.ReferenceDatasetFactory,
                factories.VisualisationCatalogueItemFactory,
            ),
        ),
        (
            "datasets:toggle_bookmark",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
                factories.ReferenceDatasetFactory,
                factories.VisualisationCatalogueItemFactory,
            ),
        ),
        (
            "datasets:usage_history",
            (
                factories.MasterDataSetFactory,
                factories.DatacutDataSetFactory,
            ),
        ),
        (
            "datasets:visualisation_usage_history",
            (factories.VisualisationCatalogueItemFactory,),
        ),
        (
            "datasets:reference_dataset_detail",
            (factories.ReferenceDatasetFactory,),
        ),
    ),
)
@pytest.mark.django_db
def test_dataset_unpublished(url_name, dataset_factories):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    for factory in dataset_factories:
        ds = factory.create(published=True)
        dataset_id = getattr(ds, "uuid", ds.id)
        response = client.get(reverse(url_name, args=(dataset_id,)))
        assert response.status_code in [200, 302]
        ds.published = False
        ds.save()
        response = client.get(reverse(url_name, args=(dataset_id,)))
        assert response.status_code == 403
        assert (
            f"This {ds.get_type_display().lower()} has not been published"
            in response.content.decode(response.charset)
        )


@pytest.mark.parametrize(
    "url_name,source_factory",
    (
        (
            "datasets:source_table_detail",
            factories.SourceTableFactory,
        ),
        (
            "datasets:custom_dataset_query_detail",
            factories.CustomDatasetQueryFactory,
        ),
    ),
)
@pytest.mark.django_db
def test_dataset_preview_permission_denied(url_name, source_factory):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    source = source_factory.create(
        dataset=factories.DataSetFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION, published=True
        ),
        data_grid_enabled=True,
    )
    response = client.get(reverse(url_name, args=(source.dataset.id, source.id)))
    assert response.status_code == 403
    assert "You do not have permission to access this dataset" in response.content.decode(
        response.charset
    )


@pytest.mark.parametrize(
    "url_name,source_factory",
    (
        (
            "datasets:source_table_detail",
            factories.SourceTableFactory,
        ),
        (
            "datasets:custom_dataset_query_detail",
            factories.CustomDatasetQueryFactory,
        ),
    ),
)
@pytest.mark.django_db
def test_dataset_preview_disabled(url_name, source_factory):
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    source = source_factory.create(
        dataset=factories.DataSetFactory.create(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION, published=True
        ),
        data_grid_enabled=False,
    )
    response = client.get(reverse(url_name, args=(source.dataset.id, source.id)))
    assert response.status_code == 403
    assert (
        f"Data preview is not enabled for this {source.dataset.get_type_display().lower()}."
        in response.content.decode(response.charset)
    )


@pytest.mark.django_db
def test_other_users_query_results(user):
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    ql = QueryLogFactory.create(run_by_user=factories.UserFactory.create())
    response = client.get(reverse("explorer:running_query", args=(ql.id,)))
    assert response.status_code == 403
    assert "You can collaborate on Data Explorer queries" in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
def test_non_admin_pipeline_access(user):
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    response = client.get(reverse("pipelines:index"))
    assert response.status_code == 403
    assert "You do not have permission to access the Pipeline builder" in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
def test_visualisations_permission_denied(user):
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    response = client.get(reverse("visualisations:root"))
    assert response.status_code == 403
    assert "You do not have permission to manage visualisations" in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.applications.views.gitlab_has_developer_access")
@mock.patch("dataworkspace.apps.applications.views._visualisation_gitlab_project")
def test_visualisations_developer_permission_required(
    mock_get_gitlab_project, mock_has_access, user
):
    user.user_permissions.add(
        Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
    )
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    visualisation = factories.VisualisationCatalogueItemFactory.create(
        visualisation_template__gitlab_project_id=1,
    )
    mock_get_gitlab_project.return_value = {
        "id": 1,
        "default_branch": "master",
        "name": "test-gitlab-project",
    }
    mock_has_access.return_value = False
    response = client.get(
        reverse(
            "visualisations:catalogue-item",
            args=(visualisation.visualisation_template.gitlab_project_id,),
        )
    )
    assert "You must be developer, maintainer or owner" in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
def test_admin_permission_denied(user):
    client = Client(raise_request_exception=False, **get_http_sso_data(user))
    response = client.get(reverse("admin:index"), follow=True)
    assert response.status_code == 403
    assert "Ask the Data Infrastructure Team for access." in response.content.decode(
        response.charset
    )
