from django.urls import reverse

from dataworkspace.tests import factories


def test_group_detail_view_redirects_to_search(client):
    response = client.get(reverse("catalogue:datagroup_item", kwargs={"slug": "test-slug"}))
    assert response.status_code == 302
    assert response["Location"] == reverse("datasets:find_datasets") + "?"


def test_old_dataset_url_redirects_to_new_url(client):
    ds = factories.DataSetFactory.create(published=True)
    response = client.get(
        reverse(
            "catalogue:dataset_fullpath",
            kwargs={"group_slug": ds.grouping.slug, "set_slug": ds.slug},
        )
    )
    assert response.status_code == 302
    assert response["Location"] == ds.get_absolute_url()


def test_old_reference_dataset_url_redirects_to_new_url(client):
    rds = factories.ReferenceDatasetFactory.create(table_name="test_detail_view")
    response = client.get(
        reverse(
            "catalogue:reference_dataset",
            kwargs={"group_slug": rds.group.slug, "reference_slug": rds.slug},
        )
    )
    assert response.status_code == 302
    assert response["Location"] == rds.get_absolute_url()
