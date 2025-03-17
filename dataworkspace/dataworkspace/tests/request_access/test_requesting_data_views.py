from unittest import TestCase

import pytest
from bs4 import BeautifulSoup
from django.test import Client
from django.urls import reverse


from dataworkspace.apps.datasets.constants import (
    SecurityClassificationAndHandlingInstructionType,
    UserAccessType,
)
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class TestRequestingData(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def assert_common_content_one_label_page(self, url_name, label):
        response = self.client.get(reverse("requesting-data-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert label in input_label

    def assert_common_content_radio_buttons_page(self, url_name, label, radio_options):
        response = self.client.get(reverse("requesting-data-step", args={(url_name)}))

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

    def test_name_page(self):
        self.assert_common_content_one_label_page(
            url_name="name", label="What is the name of the dataset?"
        )

    def test_descriptions_page(self):
        response = self.client.get(reverse("requesting-data-step", args={("descriptions")}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Summarise this dataset" in labels[0].contents[0]
        assert "Describe this dataset" in labels[1].contents[0]

    def test_origin_page(self):
        self.assert_common_content_one_label_page(
            url_name="origin", label="What type of dataset is this?"
        )

    def test_owners_page(self):
        response = self.client.get(reverse("requesting-data-step", args={("owners")}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Name of Information Asset Owner" in labels[0].contents[0]
        assert "Name of Information Asset Manager" in labels[1].contents[0]
        assert "Contact person" in labels[2].contents[0]

    def test_existing_system_page(self):
        self.assert_common_content_one_label_page(
            url_name="existing-system", label="Which system is the data set currently stored on?"
        )

    def test_previously_published_page(self):
        self.assert_common_content_one_label_page(
            url_name="previously-published",
            label="Enter the URL of where it's currently published",
        )

    def test_licence_page(self):
        self.assert_common_content_one_label_page(
            url_name="licence", label="What licence do you have for this data?"
        )

    def test_restrictions_page(self):
        self.assert_common_content_one_label_page(
            url_name="restrictions", label="What are the usage restrictions?"
        )

    def test_purpose_page(self):
        self.assert_common_content_one_label_page(
            url_name="purpose", label="What purpose has the data been collected for?"
        )

    def test_usage_page(self):
        self.assert_common_content_one_label_page(
            url_name="usage", label="What will the data be used for on Data Workspace?"
        )

    def test_security_classification_page(self):
        self.assert_common_content_radio_buttons_page(
            url_name="security-classification",
            label="What is the security classification for this data?",
            radio_options=[
                str(classification.value)
                for classification in SecurityClassificationAndHandlingInstructionType
            ],
        )

    def test_personal_data_page(self):
        self.assert_common_content_one_label_page(
            url_name="personal-data", label="Does it contain personal data?"
        )

    def test_special_personal_data_page(self):
        self.assert_common_content_one_label_page(
            url_name="special-personal-data",
            label="Does it contain special category personal data?",
        )

    def test_commercial_sensitive_page(self):
        self.assert_common_content_one_label_page(
            url_name="commercial-sensitive", label="Does it contain commercially sensitive data?"
        )

    def test_retention_period_page(self):
        self.assert_common_content_one_label_page(
            url_name="retention-period", label="What is the retention period?"
        )

    def test_update_frequency_page(self):
        self.assert_common_content_radio_buttons_page(
            url_name="update-frequency",
            label="How often is the source data updated",
            radio_options=["Constant", "Daily", "Weekly", "Other"],
        )

    def test_current_access_page(self):
        self.assert_common_content_one_label_page(
            url_name="current-access", label="Who currently has access to this dataset?"
        )

    def test_intended_access_page(self):
        response = self.client.get(reverse("requesting-data-step", args={("intended-access")}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        # header = soup.find("h1").contents[0]
        header = soup.find("h2").contents[0]
        labels = soup.find_all("label")
        assert response.status_code == 200
        # assert "Access restrictions" in header #TODO change headers for each section
        assert "Should access on Data Workspace be open to all users by request?" in header
        assert "Will this change of access have any operational impact?" in labels[2].contents[0]

    def test_location_restrictions(self):
        self.assert_common_content_one_label_page(
            url_name="location-restrictions",
            label="Should there be any location restrictions for access to this data set?",
        )

    def test_network_restrictions(self):
        self.assert_common_content_one_label_page(
            url_name="network-restrictions",
            label="Should access be limited based on device types and networks?",
        )

    def test_user_restrictions_page(self):
        self.assert_common_content_one_label_page(
            url_name="user-restrictions",
            label="Should access be restricted to certain users types?",
        )
