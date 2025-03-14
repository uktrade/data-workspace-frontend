import io
import uuid
import json
from http import HTTPStatus
from unittest import mock
from unittest.mock import patch
from unittest import TestCase
from django.test import Client

import psycopg2
from dataworkspace.apps.datasets.requesting_data.forms import DatasetCurrentAccessForm, DatasetDataOriginForm, DatasetDescriptionsForm, DatasetExistingSystemForm, DatasetLicenceForm, DatasetNameForm, DatasetOwnersForm, DatasetPreviouslyPublishedForm, DatasetPurposeForm, DatasetRestrictionsForm
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

    def test_valid_form_previously_published(self):
        self.check_for_valid_form(
            form=DatasetPreviouslyPublishedForm,
            input="""["Test previously published"]""",
            expected_response="Test previously published",
            label="previously_published"
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

    def test_valid_form_purpose(self):
        self.check_for_valid_form(
            form=DatasetPurposeForm,
            input="""["Test purpose"]""",
            expected_response="Test purpose",
            label="purpose"
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

    @patch("requests.post")
    def test_name_view(self, mock_post):
        """
        A name should be saved to the session, not call the database
        """
        response = self.client.post(
            reverse(
                "requesting-data-step",
                args=["name"],
            ),
            data={
                "wizard_current_step": "name",
                "name-name": "Test name"
            },
        )

        assert response.status_code == 200

        session_name = "Test name"

        assert mock_post.called is False
