from unittest import TestCase

from dataworkspace.apps.datasets.models import RequestingDataset
from dataworkspace.apps.datasets.constants import SecurityClassificationAndHandlingInstructionType

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
        self.requesting_dataset = RequestingDataset.objects.create()
        session = self.client.session
        session["requesting_dataset"] = self.requesting_dataset.id
        session.save()

    def assert_common_content_one_label_page(self, stage, url_name, label):

        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert " ".join(stage.split("-")).title() in header
        assert label in input_label

    def assert_common_content_radio_buttons_page(self, stage, url_name, label, radio_options):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("h2").contents[0]
        radios = soup.find_all("input", type="radio")
        radio_names = [radio.get("value").lower() for radio in radios]

        assert response.status_code == 200
        assert " ".join(stage.split("-")).title() in header
        assert label in input_label

        for option in radio_options:
            assert option.lower() in radio_names

    def assert_common_content_user_search_page(self, stage, url_name, label):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        input_label = soup.find("h2").contents[0]

        assert response.status_code == 200
        assert " ".join(stage.split("-")).title() in header
        assert label in input_label

    def assert_common_content_conditional_radio_buttons_page(self, stage, url_name, radio_label):
        response = self.client.get(reverse(f"requesting-data-{stage}-step", args={(url_name)}))

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("div", class_="govuk-label")
        radios = soup.find_all("input", type="radio")
        radio_names = [radio.get("value").lower() for radio in radios]

        assert response.status_code == 200
        assert " ".join(stage.split("-")).title() in header
        assert radio_label in labels[0].contents[0]
        assert "yes" in radio_names[0]
        assert "no" in radio_names[1]

    def test_name_page(self):
        self.assert_common_content_one_label_page(
            stage="summary-information", url_name="name", label="What is the name of the dataset?"
        )

    def test_descriptions_page(self):
        response = self.client.get(
            reverse("requesting-data-summary-information-step", args={("descriptions")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary Information" in header
        assert "Summarise this dataset" in labels[0].contents[0]
        assert "Describe this dataset" in labels[1].contents[0]

    def test_information_asset_owner_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information",
            url_name="information-asset-owner",
            label="Name of Information Asset Owner",
        )

    def test_information_asset_manager_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information",
            url_name="information-asset-manager",
            label="Name of Information Asset Manager",
        )

    def test_enquiries_contact_page(self):
        self.assert_common_content_user_search_page(
            stage="summary-information",
            url_name="enquiries-contact",
            label="Contact person",
        )

    def test_licence_page(self):
        self.assert_common_content_conditional_radio_buttons_page(
            stage="summary-information",
            url_name="licence",
            radio_label="Do you need/have a licence for this data?",
        )

    def test_security_classification_page(self):
        self.assert_common_content_radio_buttons_page(
            stage="about-this-data",
            url_name="security-classification",
            label="What is the security classification for this data?",
            radio_options=[
                str(classification.value)
                for classification in SecurityClassificationAndHandlingInstructionType
            ],
        )

    def test_personal_data_page(self):
        self.assert_common_content_conditional_radio_buttons_page(
            stage="about-this-data",
            url_name="personal-data",
            radio_label="Does it contain personal data?",
        )

    def test_special_personal_data_page(self):
        self.assert_common_content_conditional_radio_buttons_page(
            stage="about-this-data",
            url_name="special-personal-data",
            radio_label="Does it contain special category personal data?",
        )

    def test_retention_period_page(self):
        self.assert_common_content_one_label_page(
            stage="about-this-data",
            url_name="retention-period",
            label="What is the retention period?",
        )

    def test_update_frequency_page(self):
        self.assert_common_content_radio_buttons_page(
            stage="about-this-data",
            url_name="update-frequency",
            label="How often is the source data updated",
            radio_options=["Constant", "Daily", "Weekly", "Other"],
        )

    def test_intended_access_page(self):
        response = self.client.get(
            reverse("requesting-data-access-restrictions-step", args={("intended-access")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h2").contents[0]
        labels = soup.find_all("label")
        assert response.status_code == 200
        assert "Should access on Data Workspace be open to all users by request?" in header
        assert "Will this change of access have any operational impact?" in labels[2].contents[0]

    def test_user_restrictions_page(self):
        self.assert_common_content_conditional_radio_buttons_page(
            stage="access-restrictions",
            url_name="user-restrictions",
            radio_label="Should access be restricted to certain user types?",
        )
