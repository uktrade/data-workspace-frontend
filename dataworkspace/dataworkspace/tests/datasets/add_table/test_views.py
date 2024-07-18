import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.test import Client
from dataworkspace.tests import factories
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
def test_about_service():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    dataset = factories.MasterDataSetFactory.create(
        published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
    )
    print("dataset", dataset.id)
    response = client.get(
        reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
    )
    soup = BeautifulSoup(response.content.decode(response.charset))
    header_one = soup.find("h1")
    header_two = soup.find("h2")
    header_one_text = header_one.contents
    header_two_text = header_two.contents
    assert response.status_code == 200
    assert "About this service" in header_one_text
    assert "When you should not use this service" in header_two_text
