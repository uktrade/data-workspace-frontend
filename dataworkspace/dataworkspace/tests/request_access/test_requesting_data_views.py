from datetime import datetime
from unittest import TestCase

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from freezegun import freeze_time
from mock import mock

from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


        # ("security-classification", DatasetSecurityClassificationForm),
        # ("personal-data", DatasetPersonalDataForm),
        # ("special-personal-data", DatasetSpecialPersonalDataForm),
        # ("commercial-sensitive", DatasetCommercialSensitiveForm),
        # ("retention-period", DatasetRetentionPeriodForm),
        # ("update-frequency", DatasetUpdateFrequencyForm),
        # ("current-access", DatasetCurrentAccessForm),
        # ("intended-access", DatasetIntendedAccessForm),
        # ("location-restrictions", DatasetLocationRestrictionsForm),
        # ("security-clearance", DatasetSecurityClearanceForm),
        # ("network-restrictions", DatasetNetworkRestrictionsForm),
        # ("user-restrictions", DatasetUserRestrictionsForm),


@pytest.mark.django_db
class TestRequestingData(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def test_name_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("name")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What is the name of the dataset?" in label

    def test_descriptions_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("descriptions")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Summarise this dataset" in labels[0].contents[0]
        assert "Describe this dataset" in labels[1].contents[0]

    def test_origin_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("origin")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What type of dataset is this?" in label

    def test_owners_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("owners")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        labels = soup.find_all("label")

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Name of Information Asset Owner" in labels[0].contents[0]
        assert "Name of Information Asset Manager" in labels[1].contents[0]
        assert "Contact person" in labels[2].contents[0]

    def test_existing_system_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("existing-system")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Which system is the data set currently stored on?" in label

    def test_previously_published_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("previously-published")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "Enter the URL of where it's currently published" in label

    def test_licence_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("licence")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What licence do you have for this data?" in label

    def test_restrictions_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("restrictions")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What are the usage restrictions?" in label

    def test_purpose_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("purpose")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What purpose has the data been collected for?" in label

    def test_usage_page(self):
        response = self.client.get(
            reverse("requesting-data-step", args={("usage")})
        )

        soup = BeautifulSoup(response.content.decode(response.charset))
        header = soup.find("h1").contents[0]
        label = soup.find("label").contents[0]

        assert response.status_code == 200
        assert "Summary information" in header
        assert "What will the data be used for on Data Workspace?" in label