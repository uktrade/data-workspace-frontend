import io
import uuid
from datetime import date, timedelta
from urllib.parse import urlencode

import botocore
import mock
import pytest
import requests_mock
from botocore.response import StreamingBody
from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.models import NewsletterSubscription, UserSatisfactionSurvey
from dataworkspace.apps.core.utils import (
    get_notification_banner,
    is_last_days_remaining_notification_banner,
)
from dataworkspace.apps.notification_banner.models import NotificationBanner
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseTestCase, get_connect_src_from_csp, get_http_sso_data
from dataworkspace.tests.factories import UserFactory


class TestSupportViews(BaseTestCase):
    def test_landing_page(self):
        response = self._authenticated_get(reverse("support"))
        # pylint: disable=no-member
        assert response.status_code == 200
        self.assertContains(response, "I need technical support")
        self.assertContains(response, "I want to add a new dataset")
        self.assertContains(response, "I need data analysis support or advice")
        self.assertContains(response, "I need a custom visualisation reviewed")
        self.assertContains(response, "Other")

    def test_invalid_email(self):
        response = self._authenticated_post(
            reverse("support"), {"email": "notanemail", "support_type": "tech"}
        )
        assert response.status_code == 200
        self.assertContains(response, "Enter a valid email address.")

    def test_missing_email(self):
        response = self._authenticated_post(
            reverse("support"), {"email": "", "support_type": "tech"}
        )
        assert response.status_code == 200
        self.assertContains(response, "Please enter your email address")

    def test_tech_support_redirect(self):
        response = self._authenticated_post(
            reverse("support"), {"email": "a@b.com", "support_type": "tech"}
        )
        self.assertRedirects(response, f'{reverse("technical-support")}?email=a@b.com')

    def test_add_new_dataset_redirect(self):
        response = self._authenticated_post(
            reverse("support"), {"email": "a@b.com", "support_type": "dataset"}
        )
        self.assertRedirects(response, f'{reverse("add-dataset-request")}?email=a@b.com')

    @mock.patch("dataworkspace.apps.core.views.create_support_request")
    def test_other(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse("support"),
            data={
                "email": "noreply@example.com",
                "message": "A test message",
                "support_type": "other",
            },
        )
        self.assertContains(
            response,
            "Request received",
            html=True,
        )
        self.assertContains(
            response,
            "Your reference number<br /><strong>999</strong>",
            html=True,
        )
        mock_create_request.assert_called_once()

    @mock.patch("dataworkspace.apps.core.views.create_support_request")
    def test_create_tagged_support_request(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            f'{reverse("add-dataset-request")}?tag=add-dataset-request',
            data={
                "email": "noreply@example.com",
                "message": "A test message",
                "support_type": "dataset",
            },
        )
        self.assertContains(
            response,
            "Application complete",
            html=True,
        )
        self.assertContains(
            response,
            "Your reference number<br /><strong>999</strong>",
            html=True,
        )
        mock_create_request.assert_called_once_with(
            mock.ANY, "noreply@example.com", "A test message", tag="add_dataset_request"
        )

    @mock.patch("dataworkspace.apps.core.views.create_support_request")
    def test_create_tagged_support_request_unknown_tag(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse("support") + "?tag=invalid-tag",
            data={
                "email": "noreply@example.com",
                "message": "A test message",
                "support_type": "other",
            },
            post_format="multipart",
        )
        self.assertContains(
            response,
            "Request received",
            html=True,
        )
        self.assertContains(
            response,
            "Your reference number<br /><strong>999</strong>",
            html=True,
        )
        mock_create_request.assert_called_once_with(
            mock.ANY, "noreply@example.com", "A test message", tag=None
        )

    def test_tech_support_page(self):
        response = self._authenticated_get(reverse("technical-support") + "?email=a@b.com")
        # pylint: disable=no-member
        assert response.status_code == 200
        self.assertContains(response, "What were you trying to do?")
        self.assertContains(response, "What happened?")
        self.assertContains(response, "What should have happened?")

    def test_tech_support_no_email(self):
        response = self._authenticated_get(reverse("technical-support"))
        # pylint: disable=no-member
        assert response.status_code == 400

    def test_tech_support_invalid_message(self):
        response = self._authenticated_post(
            reverse("technical-support") + "?email=a@b.com",
            {
                "email": "a@b.com",
                "what_were_you_doing": "",
                "what_happened": "",
                "what_should_have_happened": "",
            },
        )
        assert response.status_code == 200
        self.assertContains(response, "Please add some detail to the support request")

    @mock.patch("dataworkspace.apps.core.views.create_support_request")
    def test_tech_support_ticket(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse("technical-support") + "?email=a@b.com",
            {
                "email": "a@b.com",
                "what_were_you_doing": "Something",
                "what_happened": "Nothing",
                "what_should_have_happened": "Something else",
            },
        )
        assert response.status_code == 200
        self.assertContains(
            response,
            "Request received",
            html=True,
        )
        self.assertContains(
            response,
            "Your reference number<br /><strong>999</strong>",
            html=True,
        )
        mock_create_request.assert_called_once_with(
            mock.ANY,
            "a@b.com",
            "What were you trying to do?\nSomething\n\n"
            "What happened?\nNothing\n\n"
            "What should have happened?\nSomething else",
        )


def test_csp_on_files_endpoint_includes_s3(client):
    response = client.get(reverse("your-files:files"))
    assert response.status_code == 200

    csp = get_connect_src_from_csp(response)

    expected_elements = [
        "dataworkspace.test:8000",
        "https://www.google-analytics.com",
        "https://s3.eu-west-2.amazonaws.com",
        "*.google-analytics.com",
        "*.analytics.google.com",
        "*.googletagmanager.com",
    ]

    for element in expected_elements:
        assert element in csp

    # fail if there are any extra csp sites
    difference = csp.difference(set(expected_elements))
    assert len(difference) == 0


@override_settings(DEBUG=False, GTM_CONTAINER_ID="test")
@pytest.mark.parametrize(
    "path_name",
    (
        "root",
        "applications:tools",
        "about",
    ),
)
def test_sso_user_id_in_gtm_datalayer(client, path_name):
    sso_id = uuid.uuid4()
    headers = {
        "HTTP_SSO_PROFILE_USER_ID": sso_id,
    }

    response = client.get(reverse(path_name), **headers)

    assert response.status_code == 200
    assert "dataLayer.push({" in response.content.decode(response.charset)
    assert f'"id": "{sso_id}"' in response.content.decode(response.charset)


@pytest.mark.parametrize("request_client", ("client", "staff_client"), indirect=["request_client"])
def test_header_links(request_client):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    header_links = soup.find("header").find_all("a")

    link_labels = [(link.get_text().strip(), link.get("href")) for link in header_links]

    expected_links = [
        ("Data Workspace", "http://dataworkspace.test:8000/"),
        (
            "Switch to Data Hub",
            "https://www.datahub.trade.gov.uk/?utm_source=Data%20Workspace"
            "&utm_medium=referral&utm_campaign=dataflow&utm_content=Switch%20to%20Data%20Hub",
        ),
        ("Home", "http://dataworkspace.test:8000/"),
        ("Data catalogue", "/datasets/"),
        ("Collections", "/collections/"),
        ("Tools", "/tools/"),
        (
            "Help centre (opens in a new tab)",
            "https://data-services-help.trade.gov.uk/data-workspace",
        ),
        ("Contact us", "/contact-us/"),
    ]

    assert link_labels == expected_links


@pytest.mark.parametrize("request_client", ("client", "staff_client"), indirect=["request_client"])
@pytest.mark.django_db
def test_footer_links(request_client):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    footer_links = soup.find("footer").find_all("a")

    link_labels = [(link.get_text().strip(), link.get("href")) for link in footer_links]

    expected_links = [
        ("Home", "http://dataworkspace.test:8000/"),
        ("Tools", "/tools/"),
        ("About", "/about/"),
        ("Contact us", "/contact-us/"),
        (
            "Help centre (opens in a new tab)",
            "https://data-services-help.trade.gov.uk/data-workspace",
        ),
        (
            "Subscribe to newsletter",
            "/newsletter_subscription/",
        ),
        (
            "Accessibility statement",
            (
                "https://data-services-help.trade.gov.uk/data-workspace/how-articles/data-workspace-basics/"
                "data-workspace-accessibility-statement/"
            ),
        ),
        (
            "Privacy Policy",
            "https://workspace.trade.gov.uk/working-at-dit/policies-and-guidance/data-workspace-privacy-policy",
        ),
        (
            "Open Government Licence v3.0",
            "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        ),
        (
            "© Crown copyright",
            "https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/"
            "uk-government-licensing-framework/crown-copyright/",
        ),
    ]

    assert link_labels == expected_links


@pytest.mark.parametrize(
    "has_quicksight_access, expected_href, expected_text",
    (
        (True, "/tools/quicksight/redirect", "Open QuickSight"),
        (
            False,
            "/request-access/self-certify",
            "Get access to QuickSight",
        ),
    ),
)
@override_settings(QUICKSIGHT_SSO_URL="https://quicksight")
@pytest.mark.django_db
def test_quicksight_link_only_shown_to_user_with_permission(
    has_quicksight_access, expected_href, expected_text
):
    user = UserFactory.create(is_staff=False, is_superuser=False)
    if has_quicksight_access:
        perm = Permission.objects.get(codename="access_quicksight")
        user.user_permissions.add(perm)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))

    content = response.content.decode(response.charset)
    soup = BeautifulSoup(content)
    quicksight_link = soup.find("a", href=True, text=expected_text)

    assert quicksight_link.get("href") == expected_href


@pytest.mark.parametrize(
    "has_quicksight_access, expected_href, expected_text",
    (
        (True, "/tools/quicksight/redirect", "Open QuickSight"),
        (
            False,
            "/request-access/self-certify",
            "Get access to QuickSight",
        ),
    ),
)
@override_settings(QUICKSIGHT_SSO_URL="https://quicksight")
@pytest.mark.django_db
def test_quicksight_link_only_shown_to_user_with_permission_with_feature_flag(
    has_quicksight_access, expected_href, expected_text
):
    user = UserFactory.create(is_staff=False, is_superuser=False)
    if has_quicksight_access:
        perm = Permission.objects.get(codename="access_quicksight")
        user.user_permissions.add(perm)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))

    content = response.content.decode(response.charset)
    soup = BeautifulSoup(content)
    quicksight_link = soup.find("a", href=True, text=expected_text)

    assert quicksight_link.get("href") == expected_href


@pytest.mark.parametrize(
    "has_appstream_update, expected_href, expected_text",
    (
        (True, "https://appstream", "Open STATA"),
        (
            False,
            "/request-access/self-certify",
            "Request access to STATA",
        ),
    ),
)
@override_settings(APPSTREAM_URL="https://appstream")
@pytest.mark.django_db
def test_appstream_link_only_shown_to_user_with_permission(
    has_appstream_update, expected_href, expected_text
):
    user = UserFactory.create(is_staff=False, is_superuser=False)
    if has_appstream_update:
        perm = Permission.objects.get(codename="access_appstream")
        user.user_permissions.add(perm)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))

    soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
    quicksight_link = soup.find("a", href=True, text=expected_text)
    assert quicksight_link.get("href") == expected_href


@pytest.mark.parametrize(
    "has_appstream_update, expected_href, expected_text",
    (
        (True, "https://appstream", "Open STATA"),
        (
            False,
            "/request-access/self-certify",
            "Get access to QuickSight",
        ),
    ),
)
@override_settings(APPSTREAM_URL="https://appstream")
@pytest.mark.django_db
def test_appstream_link_only_shown_to_user_with_permission_with_feature_flag(
    has_appstream_update, expected_href, expected_text
):
    user = UserFactory.create(is_staff=False, is_superuser=False)
    if has_appstream_update:
        perm = Permission.objects.get(codename="access_appstream")
        user.user_permissions.add(perm)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    quicksight_link = soup.find("a", href=True, text=expected_text)
    assert quicksight_link.get("href") == expected_href


@pytest.mark.parametrize(
    "expected_href, expected_text",
    (
        (
            "/request-access/self-certify",
            "Get access to QuickSight",
        ),
        (
            "/request-access/self-certify",
            "Get access to Superset",
        ),
        (
            "/request-access/self-certify",
            "Get access to Data Explorer",
        ),
        (
            "/request-access/self-certify",
            "Request access to STATA",
        ),
    ),
)
@pytest.mark.django_db
def test_tools_links_with_invalid_email(expected_href, expected_text):
    user = UserFactory.create(is_staff=False, is_superuser=False, email="ian@gmail.com")
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))
    redirected_response = client.get(expected_href)
    request_tools_access_redirect = client.get(redirected_response.url)
    request_tools_access_page = client.get(request_tools_access_redirect.url)

    soup = BeautifulSoup(response.content.decode(response.charset))
    tool_link = soup.find("a", href=True, text=expected_text)
    assert tool_link.get("href") == expected_href
    assert b"Request access to tools" in request_tools_access_page.content
    assert b"Upload file" in request_tools_access_page.content


@pytest.mark.parametrize(
    "expected_href, expected_text",
    (
        (
            "/request-access/self-certify",
            "Get access to QuickSight",
        ),
        (
            "/request-access/self-certify",
            "Get access to Superset",
        ),
        (
            "/request-access/self-certify",
            "Get access to Data Explorer",
        ),
        (
            "/request-access/self-certify",
            "Request access to STATA",
        ),
    ),
)
@pytest.mark.django_db
def test_tools_links_with_valid_email(expected_href, expected_text):
    user = UserFactory.create(is_staff=False, is_superuser=False, email="ian@trade.gov.uk")
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))
    request_tools_access_page = client.get(expected_href)
    soup = BeautifulSoup(response.content.decode(response.charset))
    tool_link = soup.find("a", href=True, text=expected_text)
    assert tool_link.get("href") == expected_href
    assert b"Get access to tools" in request_tools_access_page.content
    assert b"How to verify your training is up to date" in request_tools_access_page.content
    assert b"Enter the date that&#x27;s on your certificate" in request_tools_access_page.content


@pytest.mark.parametrize(
    "expected_href, expected_text",
    (
        (
            "/request-access/stata-access",
            "Request access to STATA",
        ),
    ),
)
@pytest.mark.django_db
def test_stata_link_after_tools_access_has_been_granted(expected_href, expected_text):
    user = UserFactory.create(is_staff=False, is_superuser=False, email="ian@trade.gov.uk")
    start_all_applications = Permission.objects.get(codename="start_all_applications")
    user.user_permissions.add(start_all_applications)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))
    redirected_response = client.get(expected_href)
    request_tools_access_page = client.get(redirected_response.url)
    soup = BeautifulSoup(response.content.decode(response.charset))
    tool_link = soup.find("a", href=True, text=expected_text)

    assert tool_link.get("href") == expected_href
    assert b"Request access to tools" in request_tools_access_page.content
    assert b"Explain why you need access to STATA" in request_tools_access_page.content


@pytest.mark.parametrize(
    "expected_href, expected_text",
    (
        (
            "/tools/quicksight/redirect",
            "Open QuickSight",
        ),
        (
            "/tools/superset/redirect",
            "Open Superset",
        ),
        (
            "/tools/explorer/redirect",
            "Open Data Explorer",
        ),
        (
            "/request-access/stata-access",
            "Request access to STATA",
        ),
    ),
)
@pytest.mark.django_db
def test_all_tool_links_after_access_has_been_granted(expected_href, expected_text):
    user = UserFactory.create(is_staff=False, is_superuser=False, email="ian@trade.gov.uk")
    permission_codenames = [
        "start_all_applications",
        "develop_visualisations",
        "access_quicksight",
    ]
    content_type = ContentType.objects.get_for_model(ApplicationInstance)
    permissions = Permission.objects.filter(
        codename__in=permission_codenames,
        content_type=content_type,
    )
    for permission in permissions:
        user.user_permissions.add(permission)
    user.save()
    client = Client(**get_http_sso_data(user))

    response = client.get(reverse("applications:tools"))
    soup = BeautifulSoup(response.content.decode(response.charset))
    tool_link = soup.find("a", href=True, text=expected_text)

    assert tool_link.get("href") == expected_href


@pytest.mark.django_db
def test_media_serve_unauthenticated(mocker, unauthenticated_client):
    mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    mock_client().head_object.side_effect = [
        botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="head_object",
        ),
    ]
    response = unauthenticated_client.get(reverse("uploaded-media") + "?path=a/path.txt")
    assert response.status_code == 403


def test_media_serve_no_path(mocker, client):
    mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    mock_client().head_object.side_effect = [
        botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="head_object",
        ),
    ]
    response = client.get(reverse("uploaded-media"))
    assert response.status_code == 400


def test_media_serve_invalid_path(mocker, client):
    mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    mock_client().head_object.side_effect = [
        botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="head_object",
        ),
    ]
    response = client.get(reverse("uploaded-media") + "?path=bad-prefix/test.txt")
    assert response.status_code == 404


def test_media_s3_error(mocker, client):
    mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    mock_client().get_object.side_effect = [
        botocore.exceptions.ClientError(
            error_response={
                "Error": {"Message": "File is a teapot"},
                "ResponseMetadata": {"HTTPStatusCode": 418},
            },
            operation_name="get_object",
        ),
    ]
    response = client.get(reverse("uploaded-media") + "?path=uploaded-media/test.txt")
    assert response.status_code == 418


def test_media_s3_valid_file(mocker, client):
    mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    file_content = b"some file content stored on s3"
    mock_client().get_object.return_value = {
        "ContentType": "text/plain",
        "ContentLength": len(file_content),
        "Body": StreamingBody(io.BytesIO(file_content), len(file_content)),
    }
    response = client.get(reverse("uploaded-media") + "?path=uploaded-media/test.txt")
    assert response.status_code == 200
    assert list(response.streaming_content)[0] == b"some file content stored on s3"
    assert response["content-length"] == str(len(b"some file content stored on s3"))


class TestDAGTaskStatus:
    @pytest.mark.parametrize("status_code", (500, 404))
    def test_dag_status_invalid(self, status_code, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}',
                status_code=status_code,
            )
            response = client.get(reverse("create-table-dag-status", args=(execution_date,)))
            assert response.status_code == status_code

    def test_dag_status(self, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}',
                json={"state": "success"},
            )
            response = client.get(reverse("create-table-dag-status", args=(execution_date,)))
            assert response.status_code == 200
            assert response.json() == {"state": "success"}

    @pytest.mark.parametrize("status_code", (500, 404))
    def test_task_status_invalid(self, status_code, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        task_id = "task-id"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}/tasks/{task_id}',
                status_code=status_code,
            )
            response = client.get(
                reverse(
                    "create-table-task-status",
                    args=(execution_date, task_id),
                )
            )
            assert response.status_code == status_code

    def test_task_status(self, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        task_id = "task-id"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}/tasks/{task_id}',
                json={"state": "success"},
            )
            response = client.get(
                reverse(
                    "create-table-task-status",
                    args=(execution_date, task_id),
                )
            )
            assert response.status_code == 200
            assert response.json() == {"state": "success"}


class TestNewsletterViews(BaseTestCase):
    def test_newsletter_defaults_to_subscribe(self):
        response = self._authenticated_get(reverse("newsletter_subscription"))

        # pylint: disable=no-member
        assert response.status_code == 200
        self.assertContains(response, "Subscribe to newsletter")

    def test_subscribe(self):
        email_address = "email@example.com"
        data = {"submit_action": "subscribe", "email": email_address}
        self._authenticated_post(reverse("newsletter_subscription"), data)

        subscription = NewsletterSubscription.objects.filter(user=self.user)
        assert subscription.exists()
        assert subscription.first().is_active
        assert subscription.first().email_address == email_address

    def test_unsubscribe(self):
        data = {"submit_action": "unsubscribe", "email": "emailis@mandatory.com"}
        self._authenticated_post(reverse("newsletter_subscription"), data)

        subscription = NewsletterSubscription.objects.filter(user=self.user)
        assert subscription.exists()
        assert not subscription.first().is_active


class TestContactUsViews(BaseTestCase):
    def test_contact_us_page_displays_expected_options(self):
        response = self._authenticated_get(reverse("contact-us"))
        # pylint: disable=no-member
        assert response.status_code == 200
        self.assertContains(response, "Get help")
        self.assertContains(response, "Give feedback")

    def test_missing_contact_type_returns_expected_error(self):
        response = self._authenticated_post(reverse("contact-us"), {"contact_type": ""})
        assert response.status_code == 200
        self.assertContains(response, "Select what you would like to do")

    def test_invalid_contact_type_returns_expected_error(self):
        response = self._authenticated_post(reverse("contact-us"), {"contact_type": "NOT_REAL"})
        assert response.status_code == 200
        self.assertContains(
            response, "Select a valid choice. NOT_REAL is not one of the available choices."
        )

    def test_get_help_redirects_to_support_page(self):
        response = self._authenticated_post(reverse("contact-us"), {"contact_type": "help"})
        assert response.status_code == 200
        self.assertRedirects(response, reverse("support"))

    def test_get_help_redirects_to_feedback_page(self):
        response = self._authenticated_post(reverse("contact-us"), {"contact_type": "feedback"})
        assert response.status_code == 200
        self.assertRedirects(response, reverse("feedback"))


@pytest.mark.django_db
class TestFeedbackViews(BaseTestCase):
    def test_missing_trying_to_do_returns_expected_error_message(self):
        response = self._authenticated_post(reverse("feedback"), {})
        assert response.status_code == 200
        self.assertContains(
            response, "Select at least one option for what were you trying to do today"
        )

    def test_missing_how_satisfied_returns_expected_error_message(self):
        response = self._authenticated_post(reverse("feedback"), {})
        assert response.status_code == 200
        self.assertContains(response, "Select how Data Workspace made you feel today")

    def test_trying_to_do_value_is_other_and_trying_to_do_other_message_missing_returns_expected_error_message(
        self,
    ):
        response = self._authenticated_post(
            reverse("feedback"), {"trying_to_do": "other", "trying_to_do_other_message": ""}
        )
        assert response.status_code == 200
        self.assertContains(response, "Enter a description for what you were doing")

    def test_trying_to_do_value_is_other_and_trying_to_do_other_message_value_present_doesnt_return_error(
        self,
    ):
        response = self._authenticated_post(
            reverse("feedback"), {"trying_to_do": "other", "trying_to_do_other_message": "Hello"}
        )
        assert response.status_code == 200
        self.assertNotContains(response, "Enter a description for what you were doing")

    def test_submitting_valid_form_adds_expected_entry_to_django(
        self,
    ):
        response = self._authenticated_post(
            reverse("feedback"),
            {
                "survey_source": "contact-us",
                "how_satisfied": "very-satisfied",
                "trying_to_do": "other",
                "trying_to_do_other_message": "Hello",
                "improve_service": "abc",
            },
        )
        assert response.status_code == 200

        survey_entry = UserSatisfactionSurvey.objects.first()
        assert survey_entry.survey_source == "contact-us"
        assert survey_entry.how_satisfied == "very-satisfied"
        assert survey_entry.trying_to_do == "other"
        assert survey_entry.trying_to_do_other_message == "Hello"
        assert survey_entry.improve_service == "abc"

    def test_survey_source_is_set_correctly_when_entering_form_from_link(self):
        url = reverse("feedback")
        params = urlencode({"survey_source": "csat-link"})
        url_with_params = f"{url}?{params}"

        response = self._authenticated_post(
            url_with_params,
            {
                "survey_source": "csat-download-link",
                "how_satisfied": "very-satisfied",
                "trying_to_do": "other",
                "trying_to_do_other_message": "Hello",
                "improve_service": "abc",
            },
        )
        assert response.status_code == 200
        survey_entry = UserSatisfactionSurvey.objects.first()
        assert survey_entry.survey_source == "csat-download-link"

    def test_trying_to_do_value_set_to_analyse_data_when_entering_from_query_params(self):
        url = reverse("feedback")
        params = urlencode({"survey_source": "csat-link"})
        url_with_params = f"{url}?{params}"

        response = self._authenticated_post(url_with_params)
        assert response.status_code == 200

        form = response.context["form"]
        assert form["trying_to_do"].initial == "analyse-data"


@pytest.mark.django_db
class TestHomeViewNotifcationBanner:
    def setUp(self, last_chance=False):
        if last_chance is True:
            self.banner = NotificationBanner.objects.create(
                campaign_name="test",
                content="content",
                end_date=date.today() + timedelta(days=3),
                last_chance_days=3,
                last_chance_content="last chance now",
                published=True,
            )
        else:
            self.banner = NotificationBanner.objects.create(
                campaign_name="test",
                content="content",
                end_date=date.today() + timedelta(days=1),
                published=True,
            )
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        self.request = RequestFactory()

    def test_get_banner_no_banner(self):
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        self.request = RequestFactory()
        request = self.request.get(reverse("root"))
        banner = get_notification_banner(request)
        assert banner is None

    def test_get_banner_not_dismissed_or_accepted(self):
        self.setUp()
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 1

        request = self.request.get(reverse("root"))
        banner = get_notification_banner(request)
        assert banner == self.banner

    def test_get_banner_accepted(self):
        self.setUp()
        self.client.cookies[self.banner.campaign_name] = "accepted"
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        request = self.request.get(reverse("root"))
        request.COOKIES[self.banner.campaign_name] = "accepted"
        banner = get_notification_banner(request)
        assert banner is None

    def test_get_banner_dismissed(self):
        self.setUp()
        self.client.cookies[self.banner.campaign_name] = "dismissed"
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        request = self.request.get(reverse("root"))
        request.COOKIES[self.banner.campaign_name] = "dismissed"
        banner = get_notification_banner(request)
        assert banner is None

    def test_get_banner_reappears_when_already_dismissed_in_last_days(self):
        self.setUp(last_chance=True)
        self.client.cookies[self.banner.campaign_name] = "dismissed"
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 1

        request = self.request.get(reverse("root"))
        request.COOKIES[self.banner.campaign_name] = "dismissed"
        banner = get_notification_banner(request)
        assert banner == self.banner

    def test_get_banner_doesnt_appear_when_already_accepted_in_last_days(self):
        self.setUp(last_chance=True)
        self.client.cookies[self.banner.campaign_name] = "accepted"
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        request = self.request.get(reverse("root"))
        request.COOKIES[self.banner.campaign_name] = "accepted"
        banner = get_notification_banner(request)
        assert banner is None

    def test_get_banner_unpublished(self):
        self.setUp()
        self.banner.published = False
        self.banner.save()
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        request = self.request.get(reverse("root"))
        banner = get_notification_banner(request)
        assert banner is None

    def test_get_banner_expired(self):
        self.setUp()
        self.banner.end_date = date.today() - timedelta(days=1)
        self.banner.save()
        response = self.client.get(reverse("root"))
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        notification_banner_div = soup.find_all("div", class_="notification-banner")
        assert len(notification_banner_div) == 0

        request = self.request.get(reverse("root"))
        banner = get_notification_banner(request)
        assert banner is None

    def test_is_not_last_days_no_last_chance(self):
        self.setUp()
        assert not is_last_days_remaining_notification_banner(self.banner)

    def test_is_last_days_when_last_day(self):
        self.setUp(last_chance=True)
        assert is_last_days_remaining_notification_banner(self.banner)

    def test_set_cookie_success(self):
        self.setUp()
        response = self.client.post(
            reverse("set_notification_cookie"),
            {"action": "accepted"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert f"banner {self.banner.campaign_name} accepted" == response.json().get("message")

    def test_set_cookie_invalid(self):
        self.setUp()
        response = self.client.post(
            reverse("set_notification_cookie"),
            {"action": "invalid"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert self.banner.campaign_name not in response.cookies
        assert "'action' parameter values must be one of:" in response.json().get("message")

    def test_set_cookie_campaign_expired(self):
        self.setUp()
        self.banner.end_date = date.today() - timedelta(days=3)
        self.banner.save()
        response = self.client.post(
            reverse("set_notification_cookie"),
            {"action": "accepted"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert self.banner.campaign_name not in response.cookies.keys()
        assert "expired" in response.json().get("message")

    def test_set_cookie_no_banner(self):
        self.user = factories.UserFactory.create(is_superuser=True)
        self.client = Client(**get_http_sso_data(self.user))
        response = self.client.post(
            reverse("set_notification_cookie"),
            {"action": "accepted"},
            content_type="application/json",
        )
        assert response.status_code == 404
        assert len(response.cookies.items()) == 0
        assert "No published notification banners available" in response.json().get("message")

    def test_set_cookie_when_dismissed_in_last_days(self):
        self.setUp(last_chance=True)
        response = self.client.post(
            reverse("set_notification_cookie"),
            {"action": "dismissed"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert self.banner.campaign_name in response.cookies
        assert "accepted" == self.client.cookies.get(self.banner.campaign_name).value
