from datetime import date, timedelta
from unittest import TestCase, mock
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.apps.request_access.views import StataAccessView
from dataworkspace.tests.common import get_http_sso_data
from dataworkspace.tests.datasets.test_views import DatasetsCommon
from dataworkspace.tests.factories import DataSetFactory
from dataworkspace.tests.request_access import factories

from dataworkspace.apps.core.storage import ClamAVResponse


class TestDatasetAccessOnly:
    def test_user_sees_appropriate_message_on_dataset_page(self, client, user, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            not in resp.content.decode(resp.charset)
        )

    def test_request_access_form_is_single_page(self, client, user, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))

        assert resp.status_code == 200
        assert "Submit" in resp.content.decode(resp.charset)

    def test_user_redirected_to_confirmation_page_after_form_submission(
        self, client, user, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.post(
            reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}),
            {"contact_email": "test@example.com", "reason_for_access": "I need it"},
        )

        access_requests = AccessRequest.objects.all()

        # Ensure summary page is shown
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )
        assert len(access_requests) == 1
        assert access_requests[0].contact_email == "test@example.com"
        assert access_requests[0].reason_for_access == "I need it"
        assert access_requests[0].journey == AccessRequest.JOURNEY_DATASET_ACCESS

        # Submit summary page
        resp = client.post(
            reverse("request_access:summary-page", kwargs={"pk": access_requests[0].pk})
        )
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:confirmation-page", kwargs={"pk": access_requests[0].pk}
        )

    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.request_access.views.zendesk.Zenpy")
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    @mock.patch("dataworkspace.zendesk.send_email")
    @override_settings(ENVIRONMENT="Production")
    def test_zendesk_ticket_created_after_form_submission(
        self, send_email, mock_upload_to_clamav, mock_zendesk_client, client, user, metadata_db
    ):
        class MockTicket:
            @property
            def ticket(self):
                return type("ticket", (object,), {"id": 1})()

        mock_zenpy_client = mock.MagicMock()
        send_email.return_value = "mock_response_id"
        mock_zenpy_client.tickets.create.return_value = MockTicket()

        mock_zendesk_client.return_value = mock_zenpy_client

        mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})

        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.post(
            reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}),
            {"contact_email": "test@example.com", "reason_for_access": "I need it"},
        )

        access_requests = AccessRequest.objects.all()

        # Ensure summary page is shown
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )

        # Submit summary page
        client.post(
            reverse("request_access:summary-page", kwargs={"pk": access_requests[0].pk}),
            {"contact_email": "test@example.com", "reason_for_access": "I need it"},
            follow=True,
        )

        assert len(mock_zenpy_client.tickets.create.call_args_list) == 1
        call_args, _ = mock_zenpy_client.tickets.create.call_args_list[0]
        ticket = call_args[0]
        dataset_url = dataset.get_absolute_url()
        assert ticket.subject == "Data set access request received - A master"
        assert (
            ticket.description
            == f"""An access request has been sent to the relevent person or team to assess you request.

There is no need to action this ticket until a further notification is received.

Data Set: A master (http://testserver/datasets/{dataset.name}#{dataset_url})

Requestor frank.exampleson@test.com
People finder link: https://people.trade.gov.uk/people-and-teams/search/?query=Frank%20Exampleson&filters=teams&filters=people

Requestor’s response to why access is needed:
I need it

Information Asset Manager: {dataset.information_asset_manager.email}

Request Approver: {dataset.information_asset_manager.email}

If access has not been granted to the requestor within 5 working days, this will trigger an update to this Zendesk ticket to resolve the request.

""")


class TestDatasetAndToolsAccess:
    def test_user_sees_appropriate_message_on_dataset_page(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200

    def test_request_access_form_is_multipage_form(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        resp = client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        assert "Continue" in resp.content.decode(resp.charset)

    def test_user_redirected_to_summary_after_dataset_request_access_form_submission(
        self, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        resp = client.post(
            reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}),
            {"contact_email": "test@example.com", "reason_for_access": "I need it"},
        )

        access_requests = AccessRequest.objects.all()

        assert len(access_requests) == 1
        assert access_requests[0].contact_email == "test@example.com"
        assert access_requests[0].reason_for_access == "I need it"
        assert access_requests[0].journey == AccessRequest.JOURNEY_DATASET_ACCESS
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )

    def test_tools_not_required_for_data_cut(self, client, metadata_db):
        datacut = DataSetFactory.create(
            published=True,
            type=DataSetType.DATACUT,
            name="A datacut",
            user_access_type="REQUIRES_AUTHORIZATION",
        )
        resp = client.post(
            reverse("request_access:dataset", kwargs={"dataset_uuid": datacut.id}),
            {"contact_email": "test@example.com", "reason_for_access": "I need it"},
        )

        access_requests = AccessRequest.objects.all()

        assert len(access_requests) == 1
        assert access_requests[0].contact_email == "test@example.com"
        assert access_requests[0].reason_for_access == "I need it"
        assert access_requests[0].journey == AccessRequest.JOURNEY_DATASET_ACCESS
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )


class TestNoAccessRequired:
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_user_sees_appropriate_message_on_request_access_page(
        self, access_type, client, user, metadata_db
    ):
        DatasetsCommon()._create_master(user_access_type=access_type)
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.get(reverse("request_access:index"))

        assert resp.status_code == 200
        assert "You have access to our tools" in resp.content.decode(resp.charset)


class TestEditAccessRequest:
    def test_edit_eligibility_criteria(self, client):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        access_request = factories.AccessRequestFactory(
            catalogue_item_id=dataset.id,
            contact_email="original@example.com",
            reason_for_access="I need it",
        )
        resp = client.post(
            reverse(
                "datasets:eligibility_criteria",
                kwargs={"dataset_uuid": dataset.id},
            )
            + f"?access_request={access_request.id}",
            {"meet_criteria": "yes"},
        )
        assert resp.status_code == 302
        assert resp.url == reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id})
        assert access_request.id == AccessRequest.objects.latest("created_date").id

    def test_edit_dataset_request_fields(self, client, user):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        access_request = factories.AccessRequestFactory(
            catalogue_item_id=dataset.id,
            contact_email="original@example.com",
            reason_for_access="I need it",
            requester=user,
        )
        resp = client.post(
            reverse(
                "request_access:dataset-request-update",
                kwargs={"pk": access_request.id},
            ),
            {
                "contact_email": "updated@example.com",
                "reason_for_access": "I still need it",
            },
        )
        assert resp.status_code == 302
        access_request.refresh_from_db()
        assert access_request.catalogue_item_id == dataset.id
        assert access_request.contact_email == "updated@example.com"
        assert access_request.reason_for_access == "I still need it"

    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    def test_edit_training_screenshot(self, mock_upload_to_clamav, mock_boto, client, user):
        mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})

        screenshot1 = SimpleUploadedFile("original-file.txt", b"file_content")
        access_request = factories.AccessRequestFactory(
            contact_email="testy-mctestface@example.com",
            training_screenshot=screenshot1,
            requester=user,
        )

        # Ensure the original file name is displayed in the form
        resp = client.get(reverse("request_access:tools", kwargs={"pk": access_request.pk}))
        assert "original-file.txt" in resp.content.decode(resp.charset)

        # Ensure the file can be updated
        screenshot2 = SimpleUploadedFile("new-file.txt", b"file_content")
        resp = client.post(
            reverse("request_access:tools", kwargs={"pk": access_request.pk}),
            {"training_screenshot": screenshot2},
        )
        assert resp.status_code == 302
        access_request.refresh_from_db()
        assert access_request.training_screenshot.name.split("!")[0] == "new-file.txt"

    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    def test_cannot_access_other_users_access_request(
        self, mock_upload_to_clamav, mock_boto, client, user
    ):
        mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})
        screenshot1 = SimpleUploadedFile("original-file.txt", b"file_content")
        access_request = factories.AccessRequestFactory(
            contact_email="testy-mctestface@example.com",
            training_screenshot=screenshot1,
        )

        # client.post results in the request.user being set to the user fixture, whereas
        # the AccessRequestFactory will create a new user object and assign it as the
        # request access requester. Therefore trying to edit the access request should
        # raise a 404
        resp = client.post(
            reverse(
                "request_access:dataset-request-update",
                kwargs={"pk": access_request.id},
            ),
            {
                "contact_email": "updated@example.com",
                "reason_for_access": "I still need it",
            },
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestSelfCertify(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(
            is_superuser=False, email="valid-domain@trade.gov.uk"
        )
        self.client = Client(**get_http_sso_data(self.user))
        self.url = reverse("request_access:self-certify-page")
        self.certificate_date = date.today() - timedelta(weeks=12)
        self.form_data = {
            "certificate_date_0": self.certificate_date.day,
            "certificate_date_1": self.certificate_date.month,
            "certificate_date_2": self.certificate_date.year,
            "declaration": True,
        }
        self.is_renewal_email_sent = True

    def test_user_sees_self_certify_form_when_email_is_allowed_to_self_certify(self):
        response = self.client.get(self.url)
        assert response.status_code == 200

    def test_user_is_redirected_to_request_access_when_email_is_not_allowed_to_self_certify(self):
        user = factories.UserFactory.create(
            is_superuser=False, email="invalid-domain@invalid.gov.uk"
        )
        client = Client(**get_http_sso_data(user))
        response = client.get(self.url)
        assert response.status_code == 302
        assert response.url == reverse("request-access:index")

    def test_certification_date_gets_saved_for_user(self):
        response = self.client.post(self.url, self.form_data)
        self.user.refresh_from_db()

        assert self.user.profile.tools_certification_date == self.certificate_date
        assert response.status_code == 302

    def test_renewal_notification_gets_reset_to_default(self):
        response = self.client.post(self.url, self.form_data)
        self.user.refresh_from_db()

        assert self.user.profile.tools_certification_date == self.certificate_date
        assert self.user.profile.is_renewal_email_sent is False
        assert response.status_code == 302

    def test_permissions_get_set_for_user(self):
        response = self.client.post(self.url, self.form_data)
        self.user.refresh_from_db()
        user_permissions = self.user.user_permissions.all()

        assert user_permissions[0].name == "Can access AWS QuickSight"
        assert user_permissions[0].codename == "access_quicksight"
        assert user_permissions[1].name == "Can start all applications"
        assert user_permissions[1].codename == "start_all_applications"
        assert user_permissions.count() == 2
        assert response.status_code == 302

    def test_form_valid_redirects_to_tools_page(self):
        response = self.client.post(self.url, self.form_data)

        assert response.url == "/tools?access=true"

    def test_self_certify_errors_for_invalid_date_format(self):
        self.form_data = {
            "certificate_date_0": "40",
            "certificate_date_1": "14",
            "certificate_date_2": "2024",
            "declaration": True,
        }
        response = self.client.post(self.url, self.form_data)

        assert (
            "The date on your Security and Data Protection certificate must be a real date"
            in str(response.content)
        )
        assert (
            "The date on your Security and Data Protection certificate must be a real date"
            in str(response.content)
        )


@pytest.mark.django_db
class TestStataAccessJourney(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(
            is_superuser=False, email="valid-domain@trade.gov.uk"
        )
        self.client = Client(**get_http_sso_data(self.user))
        self.index_url = reverse("request-access:stata-access-index")
        self.form_url = "request_access:stata-access-page"
        self.form_data = {
            "reason_for_spss_and_stata": "I want it",
        }

    def test_access_request_for_stata_redirects_to_form(self):
        response = self.client.get(self.index_url)
        redirected_response = self.client.get(response.url)
        redirected_response_content = redirected_response.content

        assert response.status_code == 302
        assert b"Request access to tools" in redirected_response_content
        assert b"Explain why you need access to STATA" in redirected_response_content

    def test_that_form_is_valid_and_redirects_to_confirmation_page(self):
        form = MagicMock()
        form.cleaned_data = self.form_data
        kwargs = {"pk": "1"}

        request = self.client.get(self.form_url, kwargs=kwargs)
        request.session = {}

        view = StataAccessView(request=request, kwargs=kwargs)

        response = view.form_valid(form=form)

        assert response.status_code == 302
        assert (
            request.session["reason_for_spss_and_stata"]
            == self.form_data["reason_for_spss_and_stata"]
        )
        assert response.url == reverse("request_access:confirmation-page", kwargs=kwargs)
