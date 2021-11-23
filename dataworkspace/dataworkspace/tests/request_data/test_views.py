import mock
import pytest
from lxml import html

from django.urls import reverse

from dataworkspace.apps.request_data.models import (
    DataRequest,
    RoleType,
    SecurityClassificationType,
    DataRequestStatus,
)
from dataworkspace.tests.request_data.factories import DataRequestFactory


class TestRequestDataIndex:
    def test_page_available(self, client):
        resp = client.get(reverse("request-data:index"))
        assert resp.status_code == 200

    def test_submitting_index_creates_data_request_for_user(self, client):
        assert DataRequest.objects.count() == 0
        resp = client.post(reverse("request-data:index"))
        assert resp.status_code == 302
        assert DataRequest.objects.count() == 1
        assert resp.url == reverse(
            "request-data:who-are-you", kwargs={"pk": DataRequest.objects.first().pk}
        )


class TestRequestDataWhoAreYou:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:who-are-you", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("role_type", ["", *RoleType.values])
    def test_page_prefills_existing_data(self, client, role_type):
        dr = DataRequestFactory.create(requester_role=role_type)
        resp = client.get(reverse("request-data:who-are-you", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        if role_type == "":
            assert len(doc.xpath('//input[@type="radio" and not(@checked)]')) == len(RoleType)

        else:
            label = RoleType(dr.requester_role).label
            element = doc.xpath(f'//input[@id = //label[contains(text(), "{label}")]/@for]')[0]
            assert element.checked is True
            assert len(doc.xpath('//input[@type="radio" and not(@checked)]')) == (
                len(RoleType) - 1
            )


class TestRequestDataOwnerOrManager:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:owner-or-manager", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("text", ["", "Mr Blobby"])
    def test_page_prefills_existing_data(self, client, text):
        dr = DataRequestFactory.create(name_of_owner_or_manager=text)
        resp = client.get(reverse("request-data:owner-or-manager", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        assert doc.xpath('//input[@type="text"]/@value') == [text]


class TestRequestDataDescription:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:describe-data", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("text", ["", "this is a description of the data"])
    def test_page_prefills_existing_data(self, client, text):
        dr = DataRequestFactory.create(data_description=text)
        resp = client.get(reverse("request-data:describe-data", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        textareas = doc.xpath("//textarea")
        assert len(textareas) == 1

        textarea = textareas[0]
        assert textarea.value == text


class TestRequestDataPurpose:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:purpose-of-data", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("text", ["", "to make a wonderful dashboard"])
    def test_page_prefills_existing_data(self, client, text):
        dr = DataRequestFactory.create(data_purpose=text)
        resp = client.get(reverse("request-data:purpose-of-data", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        textareas = doc.xpath("//textarea")
        assert len(textareas) == 1

        textarea = textareas[0]
        assert textarea.value == text


class TestRequestDataLocation:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:location-of-data", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("text", ["", "in this very easy to access API"])
    def test_page_prefills_existing_data(self, client, text):
        dr = DataRequestFactory.create(data_location=text)
        resp = client.get(reverse("request-data:location-of-data", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        textareas = doc.xpath("//textarea")
        assert len(textareas) == 1

        textarea = textareas[0]
        assert textarea.value == text


class TestRequestDataSecurityClassification:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:security-classification", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    @pytest.mark.parametrize("security_classification", ["", *SecurityClassificationType.values])
    def test_page_prefills_existing_data(self, client, security_classification):
        dr = DataRequestFactory.create(security_classification=security_classification)
        resp = client.get(reverse("request-data:security-classification", kwargs={"pk": dr.pk}))

        doc = html.fromstring(resp.content.decode(resp.charset))

        if security_classification == "":
            assert len(doc.xpath('//input[@type="radio" and not(@checked)]')) == len(
                SecurityClassificationType
            )

        else:
            label = SecurityClassificationType(dr.security_classification).label
            element = doc.xpath(f'//input[@id = //label[contains(text(), "{label}")]/@for]')[0]
            assert element.checked is True
            assert len(doc.xpath('//input[@type="radio" and not(@checked)]')) == (
                len(SecurityClassificationType) - 1
            )


class TestRequestDataCheckAnswers:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    def test_page_prefills_existing_data_for_iam_without_alternative_name(self, client):
        dr = DataRequestFactory.create(requester_role=RoleType.IAM)
        resp = client.get(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))

        body = resp.content.decode(resp.charset)
        assert dr.get_requester_role_display() in body
        assert dr.name_of_owner_or_manager not in body
        assert dr.data_description in body
        assert dr.data_purpose in body
        assert dr.data_location in body
        assert dr.get_security_classification_display() in body

    def test_page_prefills_existing_data_for_someone_else_with_alternative_name(self, client):
        dr = DataRequestFactory.create(requester_role=RoleType.other)
        resp = client.get(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))

        body = resp.content.decode(resp.charset)
        assert dr.get_requester_role_display() in body
        assert dr.name_of_owner_or_manager in body
        assert dr.data_description in body
        assert dr.data_purpose in body
        assert dr.data_location in body
        assert dr.get_security_classification_display() in body

    @pytest.mark.parametrize(
        "expected_status_code, field, value",
        (
            (400, "requester_role", "not-a-choice"),
            (400, "data_description", ""),
            (400, "data_purpose", ""),
            (302, "data_location", ""),  # field can be blank
            (400, "security_classification", ""),
            (302, "name_of_owner_or_manager", ""),  # field can be blank
        ),
    )
    @mock.patch("dataworkspace.apps.request_data.views.create_support_request")
    def test_submitting_answers_fails_on_invalid_data(
        self, create_support_request_mock, client, expected_status_code, field, value
    ):
        dr = DataRequestFactory.create(**{field: value}, status=DataRequestStatus.draft)
        create_support_request_mock.return_value = 1234

        resp = client.post(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))

        assert resp.status_code == expected_status_code

    @mock.patch("dataworkspace.apps.request_data.views.create_support_request")
    def test_submitting_data_request_that_has_been_submitted_does_not_create_new_zendesk_ticket(
        self, create_support_request_mock, client
    ):
        dr = DataRequestFactory.create(status=DataRequestStatus.submitted)
        create_support_request_mock.side_effect = Exception("should not be called")

        resp = client.post(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))

        assert resp.status_code == 302
        assert resp.url == reverse("request-data:confirmation-page", kwargs={"pk": dr.pk})
        assert create_support_request_mock.call_count == 0

    @mock.patch("dataworkspace.apps.request_data.views.create_support_request")
    def test_submitting_valid_data_request_logs_support_ticket(
        self, create_support_request_mock, client
    ):
        dr = DataRequestFactory.create(status=DataRequestStatus.draft)
        create_support_request_mock.return_value = 123456789

        resp = client.post(reverse("request-data:check-answers", kwargs={"pk": dr.pk}))

        assert resp.status_code == 302
        assert resp.url == reverse("request-data:confirmation-page", kwargs={"pk": dr.pk})
        assert create_support_request_mock.call_count == 1


class TestRequestDataConfirmationPage:
    def test_page_available(self, client):
        dr = DataRequestFactory.create()
        resp = client.get(reverse("request-data:confirmation-page", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200

    def test_shows_zendesk_ticket_id(self, client):
        dr = DataRequestFactory.create(zendesk_ticket_id="123456789-IM-A-REFERENCE-987654321")
        resp = client.get(reverse("request-data:confirmation-page", kwargs={"pk": dr.pk}))
        assert resp.status_code == 200
        assert "123456789-IM-A-REFERENCE-987654321" in resp.content.decode(resp.charset)
