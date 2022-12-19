from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.request_access.models import AccessRequest
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
        assert "You need to request access to view this data." in resp.content.decode(resp.charset)
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
    def test_zendesk_ticket_created_after_form_submission(
        self, mock_upload_to_clamav, mock_zendesk_client, client, user, metadata_db
    ):
        class MockTicket:
            @property
            def ticket(self):
                return type("ticket", (object,), {"id": 1})()

        mock_zenpy_client = mock.MagicMock()
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

        assert ticket.subject == "Access Request for A master"
        assert (
            ticket.description
            == f"""Access request for

Username:   Frank Exampleson
Journey:    Dataset access
Dataset:    A master
SSO Login:  frank.exampleson@test.com
People search: https://people.trade.gov.uk/people-and-teams/search/?query=Frank%20Exampleson&filters=teams&filters=people


Details for the request can be found at

http://testserver/admin/request_access/accessrequest/{access_requests[0].pk}/change/

"""
        )


class TestToolsAccessOnly:
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_user_sees_appropriate_message_on_dataset_page(self, access_type, client, metadata_db):
        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert "You need to request access to tools to analyse this data." in resp.content.decode(
            resp.charset
        )
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            in resp.content.decode(resp.charset)
        )

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_request_access_form_is_multipage_form(self, access_type, client, metadata_db):
        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        resp = client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        assert resp.status_code == 302
        assert resp.url == reverse("request_access:tools-1", kwargs={"pk": access_requests[0].pk})

        resp = client.get(reverse("request_access:tools-1", kwargs={"pk": access_requests[0].pk}))
        assert "Continue" in resp.content.decode(resp.charset)

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    def test_user_redirected_to_step_2_after_step_1_form_submission(
        self, mock_boto, _upload_to_clamav, access_type, client, metadata_db
    ):
        _upload_to_clamav.return_value = ClamAVResponse({"malware": False})

        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        screenshot = SimpleUploadedFile("file.txt", b"file_content")
        resp = client.post(
            reverse("request_access:tools-1", kwargs={"pk": access_requests[0].pk}),
            {"training_screenshot": screenshot},
        )

        assert len(access_requests) == 1
        assert access_requests[0].training_screenshot.name.startswith("file.txt")
        assert resp.status_code == 302
        assert resp.url == reverse("request_access:tools-2", kwargs={"pk": access_requests[0].pk})

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_user_redirected_to_step_3_after_responding_yes_in_step_2(
        self, access_type, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse("request_access:tools-2", kwargs={"pk": access_requests[0].pk}),
            {"spss_and_stata": True},
        )

        assert len(access_requests) == 1
        assert access_requests[0].spss_and_stata is True
        assert resp.status_code == 302
        assert resp.url == reverse("request_access:tools-3", kwargs={"pk": access_requests[0].pk})

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_user_redirected_to_summary_page_after_responding_no_in_step_2(
        self, access_type, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse("request_access:tools-2", kwargs={"pk": access_requests[0].pk}),
        )

        assert len(access_requests) == 1
        assert access_requests[0].spss_and_stata is False
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_user_redirected_to_summary_page_after_step_3_form_submission(
        self, access_type, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse("request_access:tools-3", kwargs={"pk": access_requests[0].pk}),
            {
                "line_manager_email_address": "manager@example.com",
                "reason_for_spss_and_stata": "I want it",
            },
        )

        assert len(access_requests) == 1
        assert access_requests[0].line_manager_email_address == "manager@example.com"
        assert access_requests[0].reason_for_spss_and_stata == "I want it"
        assert resp.status_code == 302
        assert resp.url == reverse(
            "request_access:summary-page", kwargs={"pk": access_requests[0].pk}
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    @mock.patch("dataworkspace.apps.request_access.views.zendesk.Zenpy")
    @mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
    def test_zendesk_ticket_created_after_form_submission(
        self,
        mock_upload_to_clamav,
        mock_zendesk_client,
        mock_boto,
        client,
        metadata_db,
        access_type,
    ):
        class MockTicket:
            @property
            def ticket(self):
                return type("ticket", (object,), {"id": 1})()

        mock_zenpy_client = mock.MagicMock()
        mock_zenpy_client.tickets.create.return_value = MockTicket()

        mock_zendesk_client.return_value = mock_zenpy_client

        mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})

        dataset = DatasetsCommon()._create_master(user_access_type=access_type)
        client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        access_requests = AccessRequest.objects.all()

        screenshot = SimpleUploadedFile("file.txt", b"file_content")
        client.post(
            reverse("request_access:tools-1", kwargs={"pk": access_requests[0].pk}),
            {"training_screenshot": screenshot},
        )
        client.post(
            reverse("request_access:tools-2", kwargs={"pk": access_requests[0].pk}),
            follow=True,
        )
        client.post(
            reverse("request_access:summary-page", kwargs={"pk": access_requests[0].pk}),
            follow=True,
        )

        assert len(mock_zenpy_client.tickets.create.call_args_list) == 1
        call_args, _ = mock_zenpy_client.tickets.create.call_args_list[0]
        ticket = call_args[0]

        assert ticket.subject == "Access Request for A master"
        assert (
            ticket.description
            == f"""Access request for

Username:   Frank Exampleson
Journey:    Tools access
Dataset:    A master
SSO Login:  frank.exampleson@test.com
People search: https://people.trade.gov.uk/search?search_filters[]=people&query=Frank%20Exampleson


Details for the request can be found at

http://testserver/admin/request_access/accessrequest/{access_requests[0].pk}/change/

"""
        )


class TestDatasetAndToolsAccess:
    def test_user_sees_appropriate_message_on_dataset_page(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert "You need to request access to view this data." in resp.content.decode(resp.charset)
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            in resp.content.decode(resp.charset)
        )

    def test_request_access_form_is_multipage_form(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        resp = client.get(reverse("request_access:dataset", kwargs={"dataset_uuid": dataset.id}))
        assert "Continue" in resp.content.decode(resp.charset)

    def test_user_redirected_to_tools_form_after_dataset_request_access_form_submission(
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
        assert resp.url == reverse("request_access:tools-1", kwargs={"pk": access_requests[0].pk})

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
        resp = client.get(reverse("request_access:tools-1", kwargs={"pk": access_request.pk}))
        assert "original-file.txt" in resp.content.decode(resp.charset)

        # Ensure the file can be updated
        screenshot2 = SimpleUploadedFile("new-file.txt", b"file_content")
        resp = client.post(
            reverse("request_access:tools-1", kwargs={"pk": access_request.pk}),
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
