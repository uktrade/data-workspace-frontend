import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.test import Client
from dataworkspace.tests import factories
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests.common import get_http_sso_data
from django.shortcuts import get_object_or_404

@pytest.mark.django_db
def test_about_service_page():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    dataset = factories.MasterDataSetFactory.create(
        published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
    )

    response = client.get(
        reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
    )

    soup = BeautifulSoup(response.content.decode(response.charset))
    header_one = soup.find("h1")
    header_two = soup.find("h2")
    paragraph = soup.find("p")
    header_one_text = header_one.contents
    header_two_text = header_two.contents
    paragraph_text = paragraph.contents
    assert response.status_code == 200
    assert "About this service" in header_one_text
    assert "When you should not use this service" in header_two_text
    assert (
        f"Use this service to turn a CSV file into a data table. The new table will be added to {dataset.name}."
        in paragraph_text
    )

@pytest.mark.django_db
def test_table_schema_page():
    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))
    dataset = factories.MasterDataSetFactory.create(
        published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
    )


    response = client.get(
        reverse("datasets:add_table:table-schema", kwargs={"pk": dataset.id}),
    )

    # def _get_source(self):
    #     return get_object_or_404(self.obj.sourcetable_set.all())
    
    # print('get_source',self._get_source() )

    print('response', response)
    soup = BeautifulSoup(response.content.decode(response.charset))
    header_one = soup.find("h1")
    header_two = soup.find("h2")
    paragraph = soup.find("p")
    header_one_text = header_one.contents
    header_two_text = header_two.contents
    paragraph_text = paragraph.contents
    assert response.status_code == 200
    assert "Your table’s schema" in header_one_text
    assert "Your table will be saved in schema schema" in header_two_text
    assert (
        "This is the schema used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
        in paragraph_text
    )
