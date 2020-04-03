import mock

import pytest
from bs4 import BeautifulSoup

from django.urls import reverse
from django.shortcuts import render

from dataworkspace.tests.common import BaseTestCase, get_response_csp_as_set


class TestSupportView(BaseTestCase):
    def test_create_support_request_invalid_email(self):
        response = self._authenticated_post(
            reverse('support'), {'email': 'x', 'message': 'test message'}
        )
        self.assertContains(response, 'Enter a valid email address')

    def test_create_support_request_invalid_message(self):
        response = self._authenticated_post(
            reverse('support'), {'email': 'noreply@example.com', 'message': ''}
        )
        self.assertContains(response, 'This field is required')

    @mock.patch('dataworkspace.apps.core.views.create_support_request')
    def test_create_support_request(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse('support'),
            data={'email': 'noreply@example.com', 'message': 'A test message'},
            post_format='multipart',
        )
        self.assertContains(
            response,
            'Your request has been received. Your reference is: '
            '<strong>999</strong>.',
            html=True,
        )
        mock_create_request.assert_called_once()

    @mock.patch('dataworkspace.apps.core.views.create_support_request')
    def test_create_tagged_support_request(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse('support') + '?tag=data-request',
            data={'email': 'noreply@example.com', 'message': 'A test message'},
            post_format='multipart',
        )
        self.assertContains(
            response,
            'Your request has been received. Your reference is: '
            '<strong>999</strong>.',
            html=True,
        )
        mock_create_request.assert_called_once_with(
            mock.ANY, 'noreply@example.com', 'A test message', tag='data_request'
        )

    @mock.patch('dataworkspace.apps.core.views.create_support_request')
    def test_create_tagged_support_request_unknown_tag(self, mock_create_request):
        mock_create_request.return_value = 999
        response = self._authenticated_post(
            reverse('support') + '?tag=invalid-tag',
            data={'email': 'noreply@example.com', 'message': 'A test message'},
            post_format='multipart',
        )
        self.assertContains(
            response,
            'Your request has been received. Your reference is: '
            '<strong>999</strong>.',
            html=True,
        )
        mock_create_request.assert_called_once_with(
            mock.ANY, 'noreply@example.com', 'A test message', tag=None
        )


def test_csp_on_files_endpoint_includes_s3(client):
    response = client.get(reverse('files'))
    assert response.status_code == 200

    policies = get_response_csp_as_set(response)
    assert (
        "connect-src dataworkspace.test:8000 https://s3.eu-west-2.amazonaws.com"
        in policies
    )


@pytest.mark.parametrize(
    "request_client", ('client', 'staff_client'), indirect=["request_client"]
)
def test_header_links(request_client):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    header_links = soup.find("header").find_all("a")

    link_labels = [
        (link.get_text(strip=True), link.get('href')) for link in header_links
    ]

    expected_links = [
        ("Data Workspace", "http://dataworkspace.test:8000/"),
        ("Home", "http://dataworkspace.test:8000/"),
        ("Tools", "/tools/"),
        ("About", "/about/"),
        ("Support and feedback", "/support-and-feedback/"),
        ("Help centre", "https://data-services-help.trade.gov.uk/data-workspace"),
    ]

    assert link_labels == expected_links


@pytest.mark.parametrize(
    "request_client", ("client", "staff_client"), indirect=["request_client"]
)
def test_footer_links(request_client):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    footer_links = soup.find("footer").find_all("a")

    link_labels = [
        (link.get_text(strip=True), link.get('href')) for link in footer_links
    ]

    expected_links = [
        ('Home', 'http://dataworkspace.test:8000/'),
        ("Tools", "/tools/"),
        ('About', '/about/'),
        ("Support and feedback", "/support-and-feedback/"),
        ('Help centre', 'https://data-services-help.trade.gov.uk/data-workspace'),
        (
            'Privacy Policy',
            'https://workspace.trade.gov.uk/working-at-dit/policies-and-guidance/data-workspace-privacy-policy',
        ),
        (
            'Open Government Licence v3.0',
            'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/',
        ),
        (
            '© Crown copyright',
            'https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/uk-government-licensing-framework/crown-copyright/',
        ),
    ]

    assert link_labels == expected_links


@pytest.mark.parametrize(
    "request_client, expected_template",
    (("client", "tools-unauthorised.html"), ("staff_client", "tools.html")),
    indirect=["request_client"],
)
def test_tools_only_shown_for_users_with_permissions(request_client, expected_template):
    with mock.patch(
        'dataworkspace.apps.applications.views.render', wraps=render
    ) as renderer:
        response = request_client.get(reverse("applications:tools"))

    assert response.status_code == 200
    assert renderer.call_args[0][1] == expected_template
