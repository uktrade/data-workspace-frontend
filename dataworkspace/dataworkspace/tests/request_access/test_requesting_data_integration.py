from unittest import TestCase

import pytest
from bs4 import BeautifulSoup
from django.test import Client
from django.urls import reverse


from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class TestRequestingData(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def assert_common_content_one_label_page(self, stage, url_name, label):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert label in input_label

    def assert_common_content_radio_buttons_page(self, stage, url_name, label, radio_options):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        # TODO update this in the templates to be label not h2 for consistency
        input_label = soup.find("h2").contents[0]
        radios = soup.find_all("input", type="radio")
        radio_names = [radio.get("value").lower() for radio in radios]

        assert response.status_code == 200
        assert "Summary information" in header
        assert label in input_label

        for option in radio_options:
            assert option.lower() in radio_names

    def assert_common_content_user_search_page(self, stage, url_name, label, hint):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("label").contents[0]
        hint_text = soup.find("div", class_="govuk-hint")

        assert response.status_code == 200
        assert "Summary information" in header
        assert label in input_label
        assert hint in hint_text

    def test_name_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="name", label="What is the name of the dataset?"
        )

    def test_descriptions_page(self):
        response = self.client.get(reverse("requesting-data-summary-information-step", args={("descriptions")}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Summarise this dataset" in labels[0].contents[0]
        assert "Describe this dataset" in labels[1].contents[0]

    def test_origin_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="origin", label="Where does the data come from?"
        )

    def test_information_asset_owner_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information", url_name="information-asset-owner", label="Name of Information Asset Owner", hint="IAO's are responsible for ensuring information assets are handled and managed appropriately")

    def test_information_asset_manager_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information", url_name="information-asset-manager", label="Name of Information Asset Manager", hint="IAM's have knowledge and duties associated with an asset, and so often support the IAO")

    def test_enquiries_contact_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information", url_name="enquiries-contact", label="Contact person", hint="Description of contact person")

    def test_existing_system_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="existing-system", label="Which system is the data set currently stored on?"
        )

    def test_licence_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="licence", label="What licence do you have for this data?"
        )

    def test_restrictions_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="restrictions", label="What are the usage restrictions?"
        )

    def test_usage_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="usage", label="How can this data be used on Data Workspace?"
        )

    # def test_security_classification_page(self):
    #     self.assert_common_content_radio_buttons_page(
    #         stage="about-this-data",
    #         url_name="security-classification",
    #         label="What is the security classification for this data?",
    #         radio_options=[
    #             str(classification.value)
    #             for classification in SecurityClassificationAndHandlingInstructionType
    #         ],
    #     )

    # def test_personal_data_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="about-this-data", url_name="personal-data", label="Does it contain personal data?"
    #     )

    # def test_special_personal_data_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="about-this-data",
    #         url_name="special-personal-data",
    #         label="Does it contain special category personal data?",
    #     )

    # def test_commercial_sensitive_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="about-this-data", url_name="commercial-sensitive", label="Does it contain commercially sensitive data?"
    #     )

    # def test_retention_period_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="about-this-data", url_name="retention-period", label="What is the retention period?"
    #     )

    # def test_update_frequency_page(self):
    #     self.assert_common_content_radio_buttons_page(
    #         stage="about-this-data",
    #         url_name="update-frequency",
    #         label="How often is the source data updated",
    #         radio_options=["Constant", "Daily", "Weekly", "Other"],
    #     )

    # def test_current_access_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="access-restrictions", url_name="current-access", label="Who currently has access to this dataset?"
    #     )

    # def test_intended_access_page(self):
    #     response = self.client.get(reverse("requesting-data-access-restrictions-step", args={("intended-access")}))

    #     soup = BeautifulSoup(response.content.decode(response.charset))
    #     # header = soup.find("h1").contents[0]
    #     header = soup.find("h2").contents[0]
    #     labels = soup.find_all("label")
    #     assert response.status_code == 200
    #     # assert "Access restrictions" in header #TODO change headers for each section
    #     assert "Should access on Data Workspace be open to all users by request?" in header
    #     assert "Will this change of access have any operational impact?" in labels[2].contents[0]

    # def test_location_restrictions(self):
    #     self.assert_common_content_one_label_page(
    #         stage="access-restrictions",
    #         url_name="location-restrictions",
    #         label="Should there be any location restrictions for access to this data set?",
    #     )

    # def test_network_restrictions(self):
    #     self.assert_common_content_one_label_page(
    #         stage="access-restrictions",
    #         url_name="network-restrictions",
    #         label="Should access be limited based on device types and networks?",
    #     )

    # def test_user_restrictions_page(self):
    #     self.assert_common_content_one_label_page(
    #         stage="access-restrictions",
    #         url_name="user-restrictions",
    #         label="Should access be restricted to certain users types?",
    #     )
