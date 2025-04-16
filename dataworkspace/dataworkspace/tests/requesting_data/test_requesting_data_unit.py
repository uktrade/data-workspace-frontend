from http import HTTPStatus
from unittest.mock import patch
from unittest import TestCase

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data
from dataworkspace.apps.datasets.models import RequestingDataset, SensitivityType
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetDescriptionsForm,
    DatasetEnquiriesContactForm,
    DatasetInformationAssetManagerForm,
    DatasetInformationAssetOwnerForm,
    DatasetIntendedAccessForm,
    DatasetLicenceForm,
    DatasetNameForm,
    DatasetPersonalDataForm,
    DatasetRetentionPeriodForm,
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetUpdateFrequencyForm,
    DatasetUserRestrictionsForm,
)


User = get_user_model()


@pytest.mark.django_db
class RequestingDataFormsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def check_for_valid_form(self, form, data_input, expected_response, label):
        form = form(
            {
                label: data_input,
            }
        )
        assert form.is_valid()
        if type(expected_response) == User:
            assert expected_response == form.cleaned_data[label]
        else:
            assert expected_response in form.cleaned_data[label]

    def check_for_valid_radio_conditional_form(self, form, data_input, expected_response, labels):
        form = form(
            {
                labels[0]: "yes",
                labels[1]: data_input,
            }
        )
        assert form.is_valid()
        assert "yes" in form.cleaned_data[labels[0]]
        assert expected_response in form.cleaned_data[labels[1]]

    def test_valid_form_name(self):
        self.check_for_valid_form(
            form=DatasetNameForm,
            data_input="""["Test name"]""",
            expected_response="Test name",
            label="name",
        )

    def test_valid_form_descriptions(self):
        form = DatasetDescriptionsForm(
            {
                "short_description": "Test short description",
                "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aliquam porta nunc erat, ut ultricies lorem rutrum ut. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas.",
            }
        )
        assert form.is_valid()
        assert "Test short description" in form.cleaned_data["short_description"]
        assert (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aliquam porta nunc erat, ut ultricies lorem rutrum ut. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas."
            in form.cleaned_data["description"]
        )

    @patch("django.contrib.auth.models.User.objects.get")
    def test_valid_form_information_asset_owner(self, mock_get):
        mock_get.return_value = self.user
        self.check_for_valid_form(
            form=DatasetInformationAssetOwnerForm,
            data_input="""["Test IAO"]""",
            expected_response=self.user,
            label="information_asset_owner",
        )

    @patch("django.contrib.auth.models.User.objects.get")
    def test_valid_form_information_asset_manager(self, mock_get):
        mock_get.return_value = self.user
        self.check_for_valid_form(
            form=DatasetInformationAssetManagerForm,
            data_input="""["Test IAM"]""",
            expected_response=self.user,
            label="information_asset_manager",
        )

    @patch("django.contrib.auth.models.User.objects.get")
    def test_valid_form_enquiries_contact(self, mock_get):
        mock_get.return_value = self.user
        self.check_for_valid_form(
            form=DatasetEnquiriesContactForm,
            data_input="""["Test enquiries contact"]""",
            expected_response=self.user,
            label="enquiries_contact",
        )

    def test_valid_form_licence(self):
        self.check_for_valid_radio_conditional_form(
            form=DatasetLicenceForm,
            data_input="""["Test licence"]""",
            expected_response="Test licence",
            labels=["licence_required", "licence"],
        )

    def test_valid_form_intended_access(self):
        form = DatasetIntendedAccessForm(
            {
                "intended_access": "yes",
                "operational_impact": "Test operational impact",
            }
        )
        assert form.is_valid()
        assert "yes" in form.cleaned_data["intended_access"]
        assert "Test operational impact" in form.cleaned_data["operational_impact"]

    def test_valid_form_user_restrictions(self):
        self.check_for_valid_radio_conditional_form(
            form=DatasetUserRestrictionsForm,
            data_input="""["Test user restrictions"]""",
            expected_response="Test user restrictions",
            labels=["user_restrictions_required", "user_restrictions"],
        )

    def test_valid_form_security_classification_official(self):
        form = DatasetSecurityClassificationForm(
            {
                "government_security_classification": 1,
            }
        )

        assert form.is_valid()
        assert form.cleaned_data["government_security_classification"] == 1

    def test_valid_form_security_classification_official_sensitive(self):

        sensitivity = SensitivityType.objects.all()
        form = DatasetSecurityClassificationForm(
            {
                "government_security_classification": 2,
                "sensitivity": sensitivity,
            }
        )

        assert form.is_valid()
        assert form.cleaned_data["government_security_classification"] == 2

    def test_valid_form_personal_data(self):
        self.check_for_valid_radio_conditional_form(
            form=DatasetPersonalDataForm,
            data_input="""["Test personal data"]""",
            expected_response="Test personal data",
            labels=["personal_data_required", "personal_data"],
        )

    def test_valid_form_special_personal_data(self):
        self.check_for_valid_radio_conditional_form(
            form=DatasetSpecialPersonalDataForm,
            data_input="""["Test special personal data"]""",
            expected_response="Test special personal data",
            labels=["special_personal_data_required", "special_personal_data"],
        )

    def test_valid_form_retention_period(self):
        self.check_for_valid_form(
            form=DatasetRetentionPeriodForm,
            data_input="""["Test retention period"]""",
            expected_response="Test retention period",
            label="retention_policy",
        )

    def test_valid_form_update_frequency(self):

        form = DatasetUpdateFrequencyForm(
            {
                "update_frequency": "daily",
                "message": "Test update frequency message",
            }
        )

        assert form.is_valid()
        assert "daily" in form.cleaned_data["update_frequency"]
        assert "Test update frequency message" in form.cleaned_data["message"]


@pytest.mark.django_db
class RequestingDataViewsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))
        self.requesting_dataset = RequestingDataset.objects.create()
        session = self.client.session
        session["requesting_dataset"] = self.requesting_dataset.id
        session.save()

    def check_view_response(self, stage, step, field, test="Test"):
        data = {
            f"requesting_data_{stage}_wizard_view-current_step": [step],
            f"{step}-{field}": [test],
        }
        stage = stage.replace("_", "-")

        response = self.client.post(
            reverse(
                f"requesting-data-{stage}-step",
                args=[step],
            ),
            data=data,
        )

        if step == "name":
            assert response.status_code == HTTPStatus.FOUND
        else:
            assert response.status_code == HTTPStatus.OK

    def test_name_view(self):
        self.check_view_response(stage="summary_information", step="name", field="name")

    def test_descriptions_view(self):
        data = {
            "requesting_data_summary_information_wizard_view-current_step": ["descriptions"],
            "descriptions-short_description": ["test short description"],
            "descriptions-access-description": ["test description"],
        }

        response = self.client.post(
            reverse(
                "requesting-data-summary-information-step",
                args=["descriptions"],
            ),
            data=data,
        )

        assert response.status_code == HTTPStatus.OK

    def test_information_asset_owner_view(self):
        user = get_user_model().objects.create(
            username="test.test@test.com",
            is_staff=False,
            is_superuser=False,
            email="test.test@test.com",
        )

        self.check_view_response(
            stage="summary_information",
            step="information-asset-owner",
            field="information_asset_owner",
            test=user,
        )

    def test_information_asset_manager_view(self):
        user = get_user_model().objects.create(
            username="test.test@test.com",
            is_staff=False,
            is_superuser=False,
            email="test.test@test.com",
        )

        self.check_view_response(
            stage="summary_information",
            step="information-asset-manager",
            field="information_asset_manager",
            test=user,
        )

    def test_enquiries_contact_view(self):
        user = get_user_model().objects.create(
            username="test.test@test.com",
            is_staff=False,
            is_superuser=False,
            email="test.test@test.com",
        )

        self.check_view_response(
            stage="summary_information",
            step="enquiries-contact",
            field="enquiries_contact",
            test=user,
        )

    def test_licence_view(self):
        self.check_view_response(stage="summary_information", step="licence", field="licence")

    def test_security_classification(self):
        sensitivity = SensitivityType.objects.all()

        data = {
            "requesting_data_about_this_data_wizard_view-current_step": [
                "security-classification"
            ],
            "security-classification-government_security_classification": 2,
            "security-classification-sensitivity": sensitivity,
        }

        response = self.client.post(
            reverse(
                "requesting-data-about-this-data-step",
                args=["security-classification"],
            ),
            data=data,
        )

        assert response.status_code == HTTPStatus.OK

    def test_personal_data_view(self):
        self.check_view_response(
            step="personal-data", field="personal_data", stage="about_this_data"
        )

    def test_special_personal_data_view(self):
        self.check_view_response(
            step="special-personal-data", field="special_personal_data", stage="about_this_data"
        )

    def test_retention_period_view(self):
        self.check_view_response(
            step="retention-period", field="retention_period", stage="about_this_data"
        )

    def test_update_frequency_view(self):
        self.check_view_response(
            step="update-frequency",
            field="update_frequency",
            test="constant",
            stage="about_this_data",
        )

    def test_intended_access_view(self):
        data = {
            "requesting_data_access_restrictions_wizard_view-current_step": ["intended-access"],
            "intended-access-intended_access": ["yes"],
            "intended-access-operational_impact": ["Test intended access"],
        }

        response = self.client.post(
            reverse("requesting-data-access-restrictions-step", args=["intended-access"]),
            data=data,
        )

        assert response.status_code == HTTPStatus.FOUND

    def test_user_restrictions_view(self):
        self.check_view_response(
            step="user-restrictions", field="user_restrictions", stage="access_restrictions"
        )


@pytest.mark.django_db
class RequestingDataDeleteTestCase(TestCase):

    def test_delete_modal(self):
        user = factories.UserFactory.create(is_superuser=False)
        client = Client(**get_http_sso_data(user))
        requesting_dataset = RequestingDataset.objects.create()

        response = client.get(
            reverse("delete-requesting-dataset-journey", args=[requesting_dataset.id])
        )
        assert response.status_code == 302
