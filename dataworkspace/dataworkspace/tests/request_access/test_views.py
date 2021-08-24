from unittest import mock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.tests.datasets.test_views import DatasetsCommon


class TestDatasetAccessOnly:
    def test_user_sees_appropriate_message_on_dataset_page(
        self, client, user, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert "You need to request access to view this data." in resp.content.decode(
            resp.charset
        )
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            not in resp.content.decode(resp.charset)
        )

    def test_request_access_form_is_single_page(self, client, user, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )

        assert resp.status_code == 200
        assert "Submit" in resp.content.decode(resp.charset)

    def test_user_redirected_to_confirmation_page_after_form_submission(
        self, client, user, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        resp = client.post(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id}),
            {'contact_email': 'test@example.com', 'reason_for_access': 'I need it'},
        )

        access_requests = AccessRequest.objects.all()

        assert len(access_requests) == 1
        assert access_requests[0].contact_email == 'test@example.com'
        assert access_requests[0].reason_for_access == 'I need it'
        assert access_requests[0].journey == AccessRequest.JOURNEY_DATASET_ACCESS
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:confirmation-page', kwargs={"pk": access_requests[0].pk}
        )

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.request_access.views.zendesk.Zenpy')
    def test_zendesk_ticket_created_after_form_submission(
        self, mock_zendesk_client, client, user, metadata_db
    ):
        class MockTicket:
            @property
            def ticket(self):
                return type('ticket', (object,), {'id': 1})()

        mock_zenpy_client = mock.MagicMock()
        mock_zenpy_client.tickets.create.return_value = MockTicket()

        mock_zendesk_client.return_value = mock_zenpy_client

        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user.user_permissions.add(permission)

        client.post(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id}),
            {'contact_email': 'test@example.com', 'reason_for_access': 'I need it'},
            follow=True,
        )

        access_requests = AccessRequest.objects.all()

        assert len(mock_zenpy_client.tickets.create.call_args_list) == 1
        call_args, _ = mock_zenpy_client.tickets.create.call_args_list[0]
        ticket = call_args[0]

        assert ticket.subject == 'Access Request for A master'
        assert (
            ticket.description
            == f"""Access request for

Username:   Frank Exampleson
Journey:    Dataset access
Dataset:    A master
SSO Login:  frank.exampleson@test.com
People search: https://people.trade.gov.uk/search?search_filters[]=people&query=Frank%20Exampleson


Details for the request can be found at

http://testserver/admin/request_access/accessrequest/{access_requests[0].pk}/change/

"""
        )


class TestToolsAccessOnly:
    def test_user_sees_appropriate_message_on_dataset_page(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert (
            "You need to request access to tools to analyse this data."
            in resp.content.decode(resp.charset)
        )
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            in resp.content.decode(resp.charset)
        )

    def test_request_access_form_is_multipage_form(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        resp = client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:tools-1', kwargs={"pk": access_requests[0].pk}
        )

        resp = client.get(
            reverse('request_access:tools-1', kwargs={"pk": access_requests[0].pk})
        )
        assert "Continue" in resp.content.decode(resp.charset)

    @mock.patch('dataworkspace.apps.request_access.views.models.storage.boto3')
    def test_user_redirected_to_step_2_after_step_1_form_submission(
        self, mock_boto, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        screenshot = SimpleUploadedFile("file.txt", b"file_content")
        resp = client.post(
            reverse('request_access:tools-1', kwargs={"pk": access_requests[0].pk}),
            {'training_screenshot': screenshot},
        )

        assert len(access_requests) == 1
        assert access_requests[0].training_screenshot.name.startswith('file.txt')
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:tools-2', kwargs={"pk": access_requests[0].pk}
        )

    def test_user_redirected_to_step_3_after_responding_yes_in_step_2(
        self, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse('request_access:tools-2', kwargs={"pk": access_requests[0].pk}),
            {'spss_and_stata': True},
        )

        assert len(access_requests) == 1
        assert access_requests[0].spss_and_stata is True
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:tools-3', kwargs={"pk": access_requests[0].pk}
        )

    def test_user_redirected_to_confirmation_page_after_responding_no_in_step_2(
        self, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse('request_access:tools-2', kwargs={"pk": access_requests[0].pk}),
        )

        assert len(access_requests) == 1
        assert access_requests[0].spss_and_stata is False
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:confirmation-page', kwargs={"pk": access_requests[0].pk}
        )

    def test_user_redirected_to_confirmation_page_after_step_3_form_submission(
        self, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        resp = client.post(
            reverse('request_access:tools-3', kwargs={"pk": access_requests[0].pk}),
            {
                'line_manager_email_address': 'manager@example.com',
                'reason_for_spss_and_stata': 'I want it',
            },
        )

        assert len(access_requests) == 1
        assert access_requests[0].line_manager_email_address == 'manager@example.com'
        assert access_requests[0].reason_for_spss_and_stata == 'I want it'
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:confirmation-page', kwargs={"pk": access_requests[0].pk}
        )

    @pytest.mark.django_db
    @mock.patch('dataworkspace.apps.request_access.views.models.storage.boto3')
    @mock.patch('dataworkspace.apps.request_access.views.zendesk.Zenpy')
    def test_zendesk_ticket_created_after_form_submission(
        self, mock_zendesk_client, mock_boto, client, metadata_db
    ):
        class MockTicket:
            @property
            def ticket(self):
                return type('ticket', (object,), {'id': 1})()

        mock_zenpy_client = mock.MagicMock()
        mock_zenpy_client.tickets.create.return_value = MockTicket()

        mock_zendesk_client.return_value = mock_zenpy_client

        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHENTICATION'
        )
        client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        access_requests = AccessRequest.objects.all()

        screenshot = SimpleUploadedFile("file.txt", b"file_content")
        client.post(
            reverse('request_access:tools-1', kwargs={"pk": access_requests[0].pk}),
            {'training_screenshot': screenshot},
        )
        client.post(
            reverse('request_access:tools-2', kwargs={"pk": access_requests[0].pk}),
            follow=True,
        )

        assert len(mock_zenpy_client.tickets.create.call_args_list) == 1
        call_args, _ = mock_zenpy_client.tickets.create.call_args_list[0]
        ticket = call_args[0]

        assert ticket.subject == 'Access Request for A master'
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
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        resp = client.get(dataset.get_absolute_url())

        assert resp.status_code == 200
        assert "You need to request access to view this data." in resp.content.decode(
            resp.charset
        )
        assert (
            "We will ask you some questions so we can give you access to the tools you need to analyse this data."
            in resp.content.decode(resp.charset)
        )

    def test_request_access_form_is_multipage_form(self, client, metadata_db):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        resp = client.get(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id})
        )
        assert "Continue" in resp.content.decode(resp.charset)

    def test_user_redirected_to_tools_form_after_dataset_request_access_form_submission(
        self, client, metadata_db
    ):
        dataset = DatasetsCommon()._create_master(
            user_access_type='REQUIRES_AUTHORIZATION'
        )
        resp = client.post(
            reverse('request_access:dataset', kwargs={"dataset_uuid": dataset.id}),
            {'contact_email': 'test@example.com', 'reason_for_access': 'I need it'},
        )

        access_requests = AccessRequest.objects.all()

        assert len(access_requests) == 1
        assert access_requests[0].contact_email == 'test@example.com'
        assert access_requests[0].reason_for_access == 'I need it'
        assert access_requests[0].journey == AccessRequest.JOURNEY_DATASET_ACCESS
        assert resp.status_code == 302
        assert resp.url == reverse(
            'request_access:tools-1', kwargs={"pk": access_requests[0].pk}
        )
