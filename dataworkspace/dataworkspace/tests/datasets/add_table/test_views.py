from datetime import datetime
from unittest import TestCase
from freezegun import freeze_time
import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from mock import mock
from dataworkspace.tests import factories
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class TestAddTablePagePermissions(TestCase):
    def test_user_without_permissons_get_redirected(self):
        user = factories.UserFactory.create(is_superuser=False)
        client = Client(**get_http_sso_data(user))
        dataset = factories.MasterDataSetFactory.create()

        response = client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
        )
        assert response.status_code == 302
        assert response["Location"] == f"/datasets/{dataset.id}"

    def test_iam_user_can_access_page(self):
        user = factories.UserFactory.create(is_superuser=False)
        client = Client(**get_http_sso_data(user))
        dataset = factories.MasterDataSetFactory.create(information_asset_manager=user)
        response = client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
        )
        assert response.status_code == 200

    def test_iao_user_can_access_page(self):
        user = factories.UserFactory.create(is_superuser=False)
        client = Client(**get_http_sso_data(user))
        dataset = factories.MasterDataSetFactory.create(information_asset_owner=user)
        response = client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
        )
        assert response.status_code == 200

    def test_editor_user_can_access_page(self):
        user = factories.UserFactory.create(is_superuser=False)
        client = Client(**get_http_sso_data(user))
        dataset = factories.MasterDataSetFactory.create()
        dataset.data_catalogue_editors.set([user])
        response = client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": dataset.id}),
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestAddTablePage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(information_asset_owner=self.user)

    def test_about_service_page(self):
        response = self.client.get(
            reverse("datasets:add_table:add-table", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "About this service" in header_one_text
        assert "When you should not use this service" in header_two_text
        assert (
            f"Use this service to turn a CSV file into a data table. The new table will be added to {self.dataset.name}."
            in paragraph_text
        )


@pytest.mark.django_db
class TestSchemaPage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create()
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one"
        )

    def test_table_schema_page_when_one_schema(self):
        response = self.client.get(
            reverse("datasets:add_table:table-schema", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}/add-table" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Your table's schema" in header_one_text
        assert f"Your table will be saved in '{self.source.schema}' schema" in header_two_text
        assert (
            "This is the schema used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
            in paragraph_text
        )

    def test_table_schema_page_when_multiple_schemas(self):
        self.source2 = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="dbt", table="table_two"
        )

        response = self.client.get(
            reverse("datasets:add_table:table-schema", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]
        radios = soup.find_all("input", type="radio")
        radio_names = (radio.get("value") for radio in radios)

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}/add-table" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Your table's schema" in header_one_text
        assert "Select a schema for your table" in header_two_text
        assert (
            "These are the schemas used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
            in paragraph_text
        )
        assert self.source.schema and self.source2.schema in radio_names

    def test_table_schema_page_when_all_tables_have_same_schema(self):
        self.source2 = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_two"
        )

        response = self.client.get(
            reverse("datasets:add_table:table-schema", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}/add-table" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Your table's schema" in header_one_text
        assert f"Your table will be saved in '{self.source.schema}' schema" in header_two_text
        assert (
            "This is the schema used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
            in paragraph_text
        )

    def test_table_schema_page_when_some_tables_have_same_schema(self):
        self.source2 = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="dbt", table="table_two"
        )

        response = self.client.get(
            reverse("datasets:add_table:table-schema", kwargs={"pk": self.dataset.id}),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]
        radios = soup.find_all("input", type="radio")
        radio_names = (radio.get("value") for radio in radios)

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}/add-table" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Your table's schema" in header_one_text
        assert "Select a schema for your table" in header_two_text
        assert (
            "These are the schemas used by other tables in this catalogue item. Schemas are used to categorise data sources. Schemas are often named after the data provider e.g. HMRC."
            in paragraph_text
        )

        schemas = list(radio_names)
        assert len(schemas) == 2


@pytest.mark.django_db
class TestClassificationCheckPage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one"
        )

    def test_classification_check_page(self):
        response = self.client.get(
            reverse(
                "datasets:add_table:classification-check",
                kwargs={"pk": self.dataset.id, "schema": self.source.schema},
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").contents[0]

        assert response.status_code == 200
        assert f"/datasets/{self.dataset.id}/add-table/table-schema" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Check your upload is compatible with the catalogue item" in header_one_text
        assert (
            "The security classification of the catalogue item is 'Official-Sensitive'"
            in header_two_text
        )
        assert (
            "You must not add a table that would change the security classification of the catalogue item you're adding to."
            in paragraph_text
        )


@pytest.mark.django_db
class TestDescriptiveNamePage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one"
        )

    def test_descriptive_table_name_page(self):
        response = self.client.get(
            reverse(
                "datasets:add_table:descriptive-name",
                kwargs={"pk": self.dataset.id, "schema": self.source.schema},
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        paragraph_text = soup.find("p").contents
        title_text = soup.find("title").get_text(strip=True)

        assert response.status_code == 200
        assert (
            f"/datasets/{self.dataset.id}/add-table/{self.source.schema}/classification-check"
            in backlink
        )
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Give your table a descriptive name" in header_one_text
        assert (
            "This should be a meaningful name that can help users understand what the table contains. It will show in the catalogue item under the 'Name' field in the data tables section."
            in paragraph_text
        )

    def test_error_shows_when_descriptive_table_name_input_contains_prohibited_word(self):
        words = ["record", "dataset", "data"]
        for word in words:
            response = self.client.post(
                reverse(
                    "datasets:add_table:descriptive-name",
                    kwargs={"pk": self.dataset.id, "schema": self.source.schema},
                ),
                {"descriptive_name": word},
            )

            soup = BeautifulSoup(response.content.decode(response.charset))
            error_header_text = soup.find("h2").get_text(strip=True)
            error_message_text = (
                soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
            )

            assert response.status_code == 200
            assert "There is a problem" in error_header_text
            assert f"Descriptive name cannot contain the word '{word}'" in error_message_text

    def test_error_shows_when_descriptive_table_name_input_contains_underscores(self):
        response = self.client.post(
            reverse(
                "datasets:add_table:descriptive-name",
                kwargs={"pk": self.dataset.id, "schema": self.source.schema},
            ),
            {"descriptive_name": "_"},
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert "Descriptive name cannot contain underscores" in error_message_text

    def test_error_shows_when_descriptive_table_name_is_empty(self):
        response = self.client.post(
            reverse(
                "datasets:add_table:descriptive-name",
                kwargs={"pk": self.dataset.id, "schema": self.source.schema},
            ),
            {"descriptive_name": ""},
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert "Enter a descriptive name" in error_message_text


@pytest.mark.django_db
class TestTableNamePage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            information_asset_owner=self.user,
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one", name="table_one"
        )
        self.descriptive_name = "my_table"

    def get_post_response(self, table_name):
        response = self.client.post(
            reverse(
                "datasets:add_table:table-name",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                },
            ),
            {"table_name": table_name},
        )
        return response

    def test_table_name_page(self):
        response = self.client.get(
            reverse(
                "datasets:add_table:table-name",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                },
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1").contents
        header_two_text = soup.find("h2").contents
        paragraph_text = soup.find_all("p", {"class": "govuk-body"})[1].contents[0]
        title_text = soup.find("title").get_text(strip=True)
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        label = soup.find("label").get_text(strip=True)
        help_text = soup.find("div", {"class": "govuk-hint"}).get_text(strip=True)

        assert response.status_code == 200
        assert (
            f"/datasets/{self.dataset.id}/add-table/{self.source.schema}/descriptive-name"
            in backlink
        )
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Format your table name" in header_one_text
        assert "Table names generally follow the format below" in header_two_text
        assert (
            "Your tables schema has been set to the one other tables in the catalogue item use"
            in paragraph_text
        )
        assert "Enter your table name" in label
        assert (
            "Your table name needs to be unique, have less than 42 characters and not contain any special characters apart from underscores"
            in help_text
        )

    def test_table_name_page_when_multiple_schemas(self):
        self.source2 = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="dbt", table="table_two"
        )

        response = self.client.get(
            reverse(
                "datasets:add_table:table-name",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                },
            ),
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        paragraph_text = soup.find_all("p", {"class": "govuk-body"})[1].contents[0]

        assert response.status_code == 200
        assert "You selected your table's schema in a previous screen" in paragraph_text

    def test_error_shows_when_table_name_input_contains_prohibited_word(self):
        words = ["record", "dataset", "data"]
        for word in words:
            response = self.get_post_response(word)

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert f"Table name cannot contain the word '{word}'" in error_message_text

    def test_error_shows_when_table_name_input_is_empty(self):
        response = self.get_post_response("")

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert "Enter a table name" in error_message_text

    def test_error_shows_when_table_name_input_is_over_42_characters(self):
        response = self.get_post_response("this_is_a_really_long_table_name_to_test_the_error")

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert "Table name must be 42 characters or less" in error_message_text

    def test_error_shows_when_table_name_contains_special_characters_or_numbers(self):
        invalid_names = ["specialCharacter@", "has spaces", "numbers123"]
        for invalid_name in invalid_names:
            response = self.get_post_response(invalid_name)

            soup = BeautifulSoup(response.content.decode(response.charset))
            error_header_text = soup.find("h2").get_text(strip=True)
            error_message_text = (
                soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
            )

            assert response.status_code == 200
            assert "There is a problem" in error_header_text
            assert "Table name cannot contain numbers or special characters" in error_message_text

    def test_error_shows_when_table_name_is_already_in_use(self):
        response = self.get_post_response(self.source.table)

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_header_text = soup.find("h2").get_text(strip=True)
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )

        assert response.status_code == 200
        assert "There is a problem" in error_header_text
        assert "Table name already in use" in error_message_text


@pytest.mark.django_db
class TestUploadCSVPage(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one", name="table_one"
        )
        self.descriptive_name = "my_table"
        self.table_name = "my_table_name"

    def test_upload_csv_page(self):
        response = self.client.post(
            reverse(
                "datasets:add_table:upload-csv",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                    "table_name": self.table_name,
                },
            ),
        )
        soup = BeautifulSoup(response.content.decode(response.charset))
        title_text = soup.find("title").get_text(strip=True)
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1", class_="govuk-heading-xl").get_text(strip=True)
        header_two_text = soup.find("h2", class_="govuk-heading-l").get_text(strip=True)
        paragraph_one_text = soup.find("p").get_text(strip=True)
        bullet_points = soup.find_all("ul", class_="govuk-list govuk-list--bullet")
        bullet_point_text = [
            li.get_text(strip=True)
            for bullet_point in bullet_points
            for li in bullet_point.find_all("li")
        ]
        bullet_points_two = soup.find_all(
            "ul", class_="govuk-list govuk-list--bullet govuk-!-margin-bottom-6"
        )
        bullet_point_text_two = [
            li.get_text(strip=True)
            for bullet_point_two in bullet_points_two
            for li in bullet_point_two.find_all("li")
        ]

        assert response.status_code == 200
        assert (
            f"/datasets/{self.dataset.id}/add-table/{self.source.schema}/{self.descriptive_name}/table-name"
            in backlink
        )
        assert response.status_code == 200
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Upload CSV" in header_one_text
        assert "Before you upload your CSV" in header_two_text
        assert (
            "Check your CSV against each of the below points. This can help you avoid common issues when the table is being built."
            in paragraph_one_text
        )
        assert len(bullet_point_text) + len(bullet_point_text_two) == 5

    def test_csv_upload_fails_when_it_contains_special_chars(self):
        file1 = SimpleUploadedFile(
            "sp£c!al-ch@r$.csv",
            b"id,name\r\nA1,test1\r\nA2,test2\r\n",
            content_type="text/csv",
        )

        response = self.client.post(
            reverse(
                "datasets:add_table:upload-csv",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                    "table_name": self.table_name,
                },
            ),
            data={"csv_file": file1},
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )
        assert response.status_code == 200
        assert (
            "File name cannot contain special characters apart from underscores and hyphens"
            in error_message_text
        )

    def test_csv_upload_fails_when_no_file_is_selected(self):

        response = self.client.post(
            reverse(
                "datasets:add_table:upload-csv",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                    "table_name": self.table_name,
                },
            ),
            data={"csv_file": ""},
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        error_message_text = (
            soup.find("ul", class_="govuk-list govuk-error-summary__list").find("a").contents
        )
        assert response.status_code == 200
        assert "Select a CSV" in error_message_text


@pytest.mark.django_db
class TestDataTypesView(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            information_asset_owner=self.user,
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="table_one", name="table_one"
        )
        self.descriptive_name = "my_table"
        self.table_name = "my_table_name"

    @freeze_time("2021-01-01 01:01:01")
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.datasets.add_table.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.get_s3_prefix")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.get_s3_csv_file_info")
    def test_data_types_page(
        self,
        mock_get_s3_csv_file_info,
        mock_get_s3_prefix,
        mock_copy_file,
        mock_trigger_dag,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_trigger_dag.return_value = {"execution_date": datetime.now()}
        file_info_return_value = {
            "encoding": "utf-8-sig",
            "column_definitions": [
                {
                    "header_name": "ID",
                    "column_name": "id",
                    "data_type": "text",
                    "sample_data": ["a", "b", "c"],
                },
                {
                    "header_name": "name",
                    "column_name": "name",
                    "data_type": "text",
                    "sample_data": ["d", "e", "f"],
                },
            ],
        }
        mock_get_s3_csv_file_info.return_value = file_info_return_value
        response = self.client.post(
            reverse(
                "datasets:add_table:data-types",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                    "table_name": self.table_name,
                    "file_name": "allowed_chars-.csv",
                },
            ),
        )
        assert response.status_code == 200
        soup = BeautifulSoup(response.content.decode(response.charset))
        title_text = soup.find("title").get_text(strip=True)
        backlink = soup.find("a", {"class": "govuk-back-link"}).get("href")
        header_one_text = soup.find("h1", class_="govuk-heading-xl").get_text(strip=True)
        header_two_text = soup.find("h2", class_="govuk-heading-l").get_text(strip=True)
        paragraph_one_text = soup.find("p").get_text(strip=True)
        assert f"/datasets/{self.dataset.id}" in backlink
        assert f"Add Table - {self.dataset.name} - Data Workspace" in title_text
        assert "Data Types" in header_one_text
        assert f"Choose data types for {self.table_name}" in header_two_text
        assert (
            "Data types affect the efficiency of queries. Selecting the correct data type means quicker queries and cheaper data."
            in paragraph_one_text
        )

    @freeze_time("2021-01-01 01:01:01")
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.datasets.add_table.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.get_s3_prefix")
    @mock.patch("dataworkspace.apps.datasets.add_table.views.get_s3_csv_file_info")
    def test_data_types_page_triggers_the_dag(
        self,
        mock_get_s3_csv_file_info,
        mock_get_s3_prefix,
        mock_copy_file,
        mock_trigger_dag,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_trigger_dag.return_value = {"execution_date": datetime.now()}
        file_info_return_value = {
            "encoding": "utf-8-sig",
            "column_definitions": [
                {
                    "header_name": "ID",
                    "column_name": "id",
                    "data_type": "text",
                    "sample_data": ["a", "b", "c"],
                },
                {
                    "header_name": "name",
                    "column_name": "name",
                    "data_type": "text",
                    "sample_data": ["d", "e", "f"],
                },
            ],
        }
        mock_get_s3_csv_file_info.return_value = file_info_return_value
        response = self.client.post(
            reverse(
                "datasets:add_table:data-types",
                kwargs={
                    "pk": self.dataset.id,
                    "schema": self.source.schema,
                    "descriptive_name": self.descriptive_name,
                    "table_name": self.table_name,
                    "file_name": "allowed_chars-.csv",
                },
            ),
            data={
                "path": "user/federated/abc/allowed_chars-.csv",
                "id": "text",
                "name": "text",
                "auto_generate_id_column": True,
            },
        )
        assert response.status_code == 302
        assert (
            response["Location"]
            == reverse(
                "datasets:add_table:add-table-validating",
                args=(self.dataset.id,),
            )
            + f"?descriptive_name={self.descriptive_name}&filename=allowed_chars-.csv&schema={self.source.schema}&table_name={self.table_name}&"
            f"execution_date=2021-01-01+01%3A01%3A01"
        )
        mock_copy_file.assert_called_with(
            "user/federated/abc/allowed_chars-.csv",
            "data-flow-imports/user/federated/abc/allowed_chars-.csv",
        )
        mock_trigger_dag.assert_called_with(
            {
                "file_path": "data-flow-imports/user/federated/abc/allowed_chars-.csv",
                "schema_name": self.source.schema,
                "descriptive_name": self.descriptive_name,
                "table_name": self.table_name,
                "column_definitions": file_info_return_value["column_definitions"],
                "encoding": file_info_return_value["encoding"],
                "auto_generate_id_column": True,
            },
            "DataWorkspaceS3ImportPipeline",
            f"test-{self.table_name}-2021-01-01T01:01:01",
        )


@pytest.mark.django_db
class TestAddTableConfirmation(TestCase):
    def setUp(self):
        self.database = factories.DatabaseFactory.create(memorable_name="datasets_1")
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.dataset = factories.MasterDataSetFactory.create(
            published=True,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            information_asset_owner=self.user,
            government_security_classification=2,
        )
        self.source = factories.SourceTableFactory.create(
            dataset=self.dataset, schema="test", table="my_table_name"
        )
        self.descriptive_name = "my_table"
        self.table_name = "my_table_name"

    def test_confirmation_page(self):
        response = self.client.get(
            reverse("datasets:add_table:add-table-success", kwargs={"pk": self.dataset.id})
            + f"?descriptive_name={self.descriptive_name}&filename=allowed_chars-.csv&schema={self.source.schema}&table_name={self.table_name}&"
            f"execution_date=2021-01-01+01%3A01%3A01",
        )
        soup = BeautifulSoup(response.content.decode(response.charset))
        panel_header_one = soup.find("h1", {"class": "govuk-panel__title"}).contents[0]
        panel_body = soup.find("div", {"class": "govuk-panel__body"}).contents[0]
        back_link = soup.find("a", {"id": "backlink"}).attrs["href"]
        edit_link = soup.find("a", {"id": "editlink"}).attrs["href"]
        preview_link = soup.find("a", {"id": "previewlink"}).attrs["href"]
        dataset_id = str(self.dataset.id)
        assert response.status_code == 200
        assert "Table added" == panel_header_one
        assert self.source.name in panel_body
        assert dataset_id in back_link
        assert dataset_id in edit_link
        assert dataset_id in preview_link

    @mock.patch("dataworkspace.apps.datasets.add_table.views.log_event")
    def test_event_log_has_been_added(self, mock_log_event):
        response = self.client.get(
            reverse("datasets:add_table:add-table-success", kwargs={"pk": self.dataset.id})
            + f"?descriptive_name={self.descriptive_name}&filename=allowed_chars-.csv&schema={self.source.schema}&table_name={self.table_name}&"
            f"execution_date=2021-01-01+01%3A01%3A01",
        )
        mock_log_event.assert_called_with(self.user, event_type=57, related_object=self.dataset)
        assert response.status_code == 200
