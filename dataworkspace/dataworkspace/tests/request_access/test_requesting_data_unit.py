import io
import uuid
import json
from http import HTTPStatus
from unittest import mock
from unittest.mock import patch
from unittest import TestCase
from django.test import Client

import psycopg2
from dataworkspace.apps.datasets.requesting_data.forms import DatasetDataOriginForm, DatasetDescriptionsForm, DatasetExistingSystemForm, DatasetLicenceForm, DatasetNameForm, DatasetOwnersForm, DatasetRestrictionsForm
import pytest
from botocore.response import StreamingBody
from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import DataSet, SourceLink
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@pytest.mark.django_db
class RequestingDataFormsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def check_for_valid_form(self, form, input, expected_response, label):
        form = form({label: input,})
        assert form.is_valid()
        assert expected_response in form.cleaned_data[label]

    def test_valid_form_name(self):
        self.check_for_valid_form(
            form=DatasetNameForm,
            input="""["Test name"]""",
            expected_response="Test name",
            label="name"
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
            label="origin"
        )

    @patch("django.contrib.auth.models.User.objects.get")
    def test_valid_form_owners(self, mock_get):
        mock_get.return_value = self.user
        form = DatasetOwnersForm(
            {
                "information_asset_owner": "Testy test",
                "information_asset_manager": "Testy test",
                "enquiries_contact": "Testy test",
            }
        )

        assert form.is_valid()
        assert form.cleaned_data["information_asset_owner"] == self.user
        assert form.cleaned_data["information_asset_manager"] == self.user
        assert form.cleaned_data["enquiries_contact"] == self.user

    def test_valid_form_existing_system(self):
        self.check_for_valid_form(
            form=DatasetExistingSystemForm,
            input="""["Test existing system"]""",
            expected_response="Test existing system",
            label="existing_system"
        )

    def test_valid_form_licence(self):
        self.check_for_valid_form(
            form=DatasetLicenceForm,
            input="""["Test licence"]""",
            expected_response="Test licence",
            label="licence"
        )

    def test_valid_form_restrictions(self):
        self.check_for_valid_form(
            form=DatasetRestrictionsForm,
            input="""["Test restrictions"]""",
            expected_response="Test restrictions",
            label="restrictions"
        )

    def test_valid_form_usage(self):
        pass

    def test_valid_form_current_access(self):
        pass

    def test_valid_form_intended_access(self):
        pass

    def test_valid_form_location_restrictions(self):
        pass

    def test_valid_form_security_clearance(self):
        pass

    def test_valid_form_network_restrictions(self):
        pass

    def test_valid_form_user_restrictions(self):
        pass
    
    def test_valid_form_security_classification(self):
        pass

    def test_valid_form_personal_data(self):
        pass

    def test_valid_form_special_personal_data(self):
        pass

    def test_valid_form_commercial_sensitive_form(self):
        pass

    def test_valid_form_retention_period(self):
        pass

    def test_valid_form_update_frequency(self):
        pass



@pytest.mark.django_db
class RequestingDataViewsTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory.create(is_superuser=False)
        self.client = Client(**get_http_sso_data(self.user))

    def check_view_response(self, step, field):
        data = {
            "requesting_data_wizard_view-current_step": [step],
            f"{step}-{field}": [f"Test {field}"],
        }

        response = self.client.post(
            reverse(
                "requesting-data-step",
                args=[step],
            ),
            data=data,
        )

        return response

    @patch("requests.post")
    def test_name_view(self, mock_post):
        response = self.check_view_response(step="name", field="name")
        assert response.status_code == HTTPStatus.FOUND
        assert mock_post.called is False

    def test_descriptions_view(self):
        pass

    @patch("requests.post")
    def test_origin_view(self, mock_post):
        response = self.check_view_response(step="origin", field="origin")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_owners_view(self, mock_post):
        pass

    @patch("requests.post")
    def test_existing_system_view(self, mock_post):
        response = self.check_view_response(step="existing-system", field="existing_system")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_licence_view(self, mock_post):
        response = self.check_view_response(step="licence", field="licence")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_restrictions_view(self, mock_post):
        response = self.check_view_response(step="restrictions", field="restrictions")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_usage_view(self, mock_post):
        response = self.check_view_response(step="usage", field="usage")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_intended_access_view(self, mock_post):
        pass

    @patch("requests.post")
    def test_personal_data_view(self, mock_post):
        response = self.check_view_response(step="personal-data", field="personal_data")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_special_personal_data_view(self, mock_post):
        response = self.check_view_response(step="special-personal-data", field="special_personal_data")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_commercial_sensitive_form_view(self, mock_post):
        response = self.check_view_response(step="commercial-sensitive", field="commercial_sensitive")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_retention_period_view(self, mock_post):
        response = self.check_view_response(step="retention-period", field="retention_period")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_update_frequency_view(self, mock_post):
        pass

    @patch("requests.post")
    def test_intended_access_view(self, mock_post):
        pass

    @patch("requests.post")
    def test_location_restrictions_view(self, mock_post):
        response = self.check_view_response(step="location-restrictions", field="location_restrictions")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_network_restrictions_view(self, mock_post):
        response = self.check_view_response(step="network-restrictions", field="network_restrictions")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

    @patch("requests.post")
    def test_user_restrictions_view(self, mock_post):
        response = self.check_view_response(step="user-restrictions", field="user_restrictions")
        assert response.status_code == HTTPStatus.OK
        assert mock_post.called is False

