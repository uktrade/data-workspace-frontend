import pytest
from django.test import Client
from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


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
            "datasets:reference_dataset_grid",
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
