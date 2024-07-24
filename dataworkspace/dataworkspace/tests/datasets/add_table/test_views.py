from unittest import TestCase
import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.test import Client
from dataworkspace.tests import factories
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class TestAddTable(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            information_asset_owner=self.user,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table1"
        )

    def test_about_service_page(self):
        response = self.client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header_one = soup.find("h1")
        header_two = soup.find("h2")
        paragraph = soup.find("p")
        title = soup.find("title")
        header_one_text = header_one.contents
        header_two_text = header_two.contents
        paragraph_text = paragraph.contents
        title_text = title.contents[0]

        assert response.status_code == 200
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "About this service" in header_one_text
        assert "When you should not use this service" in header_two_text
        assert (
            f"Use this service to turn a CSV file into a data table. The new table will be added to {self.dataset.name}."
            in paragraph_text
        )

    def test_table_schema_page(self):
        response = self.client.get(
            reverse("datasets:add_table:table-schema", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header_one = soup.find("h1")
        header_two = soup.find("h2")
        paragraph = soup.find("p")
        title = soup.find("title")
        header_one_text = header_one.contents
        header_two_text = header_two.contents
        paragraph_text = paragraph.contents
        title_text = title.contents[0]

        assert response.status_code == 200
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Your table's schema" in header_one_text
        assert f"Your table will be saved in '{self.source.schema}' schema" in header_two_text
        assert (
            "This is the schema used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
            in paragraph_text
        )

    def test_classification_check_page(self):
        response = self.client.get(
            reverse("datasets:add_table:classification-check", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header_one = soup.find("h1")
        header_two = soup.find("h2")
        paragraph = soup.find("p")
        title = soup.find("title")
        header_one_text = header_one.contents
        header_two_text = header_two.contents
        paragraph_text = paragraph.contents
        title_text = title.contents[0]

        assert response.status_code == 200
        assert f"Classification check - {self.dataset.name} - Data Workspace" in title_text
        assert "Check your upload is compatible with the catalogue item" in header_one_text
        assert (
            f"The security classification of the catalogue item is {{model.get_government_security_classification_display}}"
            in header_two_text
        )
        assert "By clicking 'continue', you're confirming your upload:" in paragraph_text
