from http import HTTPStatus
from unittest.mock import patch
from unittest import TestCase
from django.contrib.auth import get_user_model

from django.test import Client

from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetDataOriginForm,
    DatasetDescriptionsForm,
    DatasetExistingSystemForm,
    DatasetLicenceForm,
    DatasetNameForm,
    DatasetRestrictionsForm,
    DatasetUsageForm,
)
import pytest

from django.urls import reverse

from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class RequestingDataFormsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def check_for_valid_form(self, form, input, expected_response, label):
        form = form(
            {
                label: input,
            }
        )
        assert form.is_valid()
        assert expected_response in form.cleaned_data[label]

    def test_valid_form_name(self):
        self.check_for_valid_form(
            form=DatasetNameForm,
            input="""["Test name"]""",
            expected_response="Test name",
            label="name",
        )

    def test_valid_form_descriptions(self):
        form = DatasetDescriptionsForm(
            {
                "short_description": "Test short description",
                "description": "Test description",
            }
        )
        assert form.is_valid()
        assert "Test short description" in form.cleaned_data["short_description"]
        assert "Test description" in form.cleaned_data["description"]

    def test_valid_form_origin(self):
        self.check_for_valid_form(
            form=DatasetDataOriginForm,
            input="""["Test origin"]""",
            expected_response="Test origin",
            label="origin",
        )

    @patch("django.contrib.auth.models.User.objects.get")
    def test_valid_form_owners(self, mock_get):
        pass
        # mock_get.return_value = self.user
        # form = DatasetOwnersForm(
        #     {
        #         "information_asset_owner": "Testy test",
        #         "information_asset_manager": "Testy test",
        #         "enquiries_contact": "Testy test",
        #     }
        # )

        # assert form.is_valid()
        # assert form.cleaned_data["information_asset_owner"] == self.user
        # assert form.cleaned_data["information_asset_manager"] == self.user
        # assert form.cleaned_data["enquiries_contact"] == self.user

    def test_valid_form_existing_system(self):
        self.check_for_valid_form(
            form=DatasetExistingSystemForm,
            input="""["Test existing system"]""",
            expected_response="Test existing system",
            label="existing_system",
        )

    def test_valid_form_licence(self):
        self.check_for_valid_form(
            form=DatasetLicenceForm,
            input="""["Test licence"]""",
            expected_response="Test licence",
            label="licence",
        )

    def test_valid_form_restrictions(self):
        self.check_for_valid_form(
            form=DatasetRestrictionsForm,
            input="""["Test restrictions"]""",
            expected_response="Test restrictions",
            label="restrictions",
        )

    def test_valid_form_usage(self):
        self.check_for_valid_form(
            form=DatasetUsageForm,
            input="""["Test usage"]""",
            expected_response="Test usage",
            label="usage",
        )

    # def test_valid_form_intended_access(self):

    #     form = DatasetIntendedAccessForm(
    #         {
    #             "intended_access": "yes",
    #             "operational_impact": "Test operational impact",
    #         }
    #     )
    #     assert form.is_valid()
    #     assert "yes" in form.cleaned_data["intended_access"]
    #     assert "Test operational impact" in form.cleaned_data["operational_impact"]

    # def test_valid_form_location_restrictions(self):
    #     self.check_for_valid_form(
    #         form=DatasetLocationRestrictionsForm,
    #         input="""["Test location restrictions"]""",
    #         expected_response="Test location restrictions",
    #         label="location_restrictions",
    #     )

    # def test_valid_form_network_restrictions(self):
    #     self.check_for_valid_form(
    #         form=DatasetNetworkRestrictionsForm,
    #         input="""["Test network restrictions"]""",
    #         expected_response="Test network restrictions",
    #         label="network_restrictions",
    #     )

    # def test_valid_form_user_restrictions(self):
    #     self.check_for_valid_form(
    #         form=DatasetUserRestrictionsForm,
    #         input="""["Test user restrictions"]""",
    #         expected_response="Test user restrictions",
    #         label="user_restrictions",
    #     )

    # def test_valid_form_security_classification_official(self):
    #     form = DatasetSecurityClassificationForm(
    #         {
    #             "government_security_classification": 1,
    #         }
    #     )

    #     assert form.is_valid()
    #     assert form.cleaned_data["government_security_classification"] == 1

    # def test_valid_form_security_classification_official_sensitive(self):

    #     sensitivity = SensitivityType.objects.all()
    #     form = DatasetSecurityClassificationForm(
    #         {
    #             "government_security_classification": 2,
    #             "sensitivity": sensitivity,
    #         }
    #     )

    #     assert form.is_valid()
    #     assert form.cleaned_data["government_security_classification"] == 2

    # def test_valid_form_personal_data(self):
    #     self.check_for_valid_form(
    #         form=DatasetPersonalDataForm,
    #         input="""["Test personal data"]""",
    #         expected_response="Test personal data",
    #         label="personal_data",
    #     )

    # def test_valid_form_special_personal_data(self):
    #     self.check_for_valid_form(
    #         form=DatasetSpecialPersonalDataForm,
    #         input="""["Test special personal data"]""",
    #         expected_response="Test special personal data",
    #         label="special_personal_data",
    #     )

    # def test_valid_form_commercial_sensitive_form(self):
    #     self.check_for_valid_form(
    #         form=DatasetCommercialSensitiveForm,
    #         input="""["Test commercial personal data"]""",
    #         expected_response="Test commercial personal data",
    #         label="commercial_sensitive",
    #     )

    # def test_valid_form_retention_period(self):
    #     self.check_for_valid_form(
    #         form=DatasetRetentionPeriodForm,
    #         input="""["Test retention period"]""",
    #         expected_response="Test retention period",
    #         label="retention_policy",
    #     )

    # def test_valid_form_update_frequency(self):

    #     form = DatasetUpdateFrequencyForm(
    #         {
    #             "update_frequency": "daily",
    #             "message": "Test update frequency message",
    #         }
    #     )

    #     assert form.is_valid()
    #     assert "daily" in form.cleaned_data["update_frequency"]
    #     assert "Test update frequency message" in form.cleaned_data["message"]


@pytest.mark.django_db
class RequestingDataViewsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    @patch("requests.post")
    def check_view_response(self, mock_post, stage, step, field, test="Test"):
        data = {
            f"requesting_data_{stage}_wizard_view-current_step": [step],
            f"{step}-{field}": [test],
        }

        response = self.client.post(
            reverse(
                "requesting-data-summary-information-step",
                args=[step],
            ),
            data=data,
        )

        if step == "name":
            assert response.status_code == HTTPStatus.FOUND
        else:
            assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    def test_name_view(self):
        self.check_view_response(stage="summary_information", step="name", field="name")

    @patch("requests.post")
    def test_descriptions_view(self, mock_post):
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
        assert mock_post.called is False

    def test_origin_view(self):
        self.check_view_response(stage="summary_information", step="origin", field="origin")

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

    def test_existing_system_view(self):
        self.check_view_response(
            stage="summary_information", step="existing-system", field="existing_system"
        )

    def test_licence_view(self):
        self.check_view_response(stage="summary_information", step="licence", field="licence")

    def test_restrictions_view(self):
        self.check_view_response(
            stage="summary_information", step="restrictions", field="restrictions"
        )

    def test_usage_view(self):
        self.check_view_response(stage="summary_information", step="usage", field="usage")

    # @patch("requests.post")
    # def test_security_classification(self, mock_post):
    #     sensitivity = SensitivityType.objects.all()

    #     data = {
    #         "requesting_data_wizard_view-current_step": ["security-classification"],
    #         "security-classification-government_security_classification": 2,
    #         "security-classification-sensitivity": sensitivity,
    #     }

    #     response = self.client.post(
    #         reverse(
    #             "requesting-data-step",
    #             args=["security-classification"],
    #         ),
    #         data=data,
    #     )

    #     assert response.status_code == HTTPStatus.OK
    #     assert mock_post.called is False

    # def test_personal_data_view(self):
    #     self.check_view_response(step="personal-data", field="personal_data")

    # def test_special_personal_data_view(self):
    #     self.check_view_response(step="special-personal-data", field="special_personal_data")

    # def test_commercial_sensitive_view(self):
    #     self.check_view_response(step="commercial-sensitive", field="commercial_sensitive")

    # def test_retention_period_view(self):
    #     self.check_view_response(step="retention-period", field="retention_period")

    # def test_update_frequency_view(self):
    #     self.check_view_response(
    #         step="update-frequency", field="update_frequency", test="constant"
    #     )

    # @patch("requests.post")
    # def test_intended_access_view(self, mock_post):
    #     data = {
    #         "requesting_data_wizard_view-current_step": ["intended-access"],
    #         "intended-access-intended_access": ["yes"],
    #         "intended-access-operational_impact": ["Test intended access"],
    #     }

    #     response = self.client.post(
    #         reverse(
    #             "requesting-data-step",
    #             args=["intended-access"],
    #         ),
    #         data=data,
    #     )

    #     assert response.status_code == HTTPStatus.OK
    #     assert mock_post.called is False

    # def test_location_restrictions_view(self):
    #     self.check_view_response(step="location-restrictions", field="location_restrictions")

    # def test_network_restrictions_view(self):
    #     self.check_view_response(step="network-restrictions", field="network_restrictions")

    # def test_user_restrictions_view(self):
    #     self.check_view_response(step="user-restrictions", field="user_restrictions")
