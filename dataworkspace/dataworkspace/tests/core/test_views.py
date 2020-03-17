import mock
import pytest
from bs4 import BeautifulSoup

from django.urls import reverse

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


def test_csp_on_files_endpoint_includes_s3(client):
    response = client.get(reverse('files'))
    assert response.status_code == 200

    policies = get_response_csp_as_set(response)
    assert (
        "connect-src dataworkspace.test:8000 https://s3.eu-west-2.amazonaws.com"
        in policies
    )


@pytest.mark.parametrize(
    "request_client, expected_links",
    (
        (
            "client",
            [
                ("Data Workspace", "http://dataworkspace.test:8000/"),
                ("Home", "http://dataworkspace.test:8000/"),
                ("About", "/about/"),
                (
                    "Help centre",
                    "https://data-services-help.trade.gov.uk/data-workspace",
                ),
            ],
        ),
        (
            "staff_client",
            [
                ("Data Workspace", "http://dataworkspace.test:8000/"),
                ("Home", "http://dataworkspace.test:8000/"),
                ("Tools", "/tools/"),
                ("About", "/about/"),
                (
                    "Help centre",
                    "https://data-services-help.trade.gov.uk/data-workspace",
                ),
            ],
        ),
    ),
    indirect=["request_client"],
)
def test_header_links(request_client, expected_links):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    header_links = soup.find("header").find_all("a")

    link_labels = [
        (link.get_text(strip=True), link.get('href')) for link in header_links
    ]

    assert link_labels == expected_links


@pytest.mark.parametrize(
    "request_client, expected_links",
    (
        (
            "client",
            [
                ('Home', 'http://dataworkspace.test:8000/'),
                ('About', '/about/'),
                (
                    'Help centre',
                    'https://data-services-help.trade.gov.uk/data-workspace',
                ),
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
            ],
        ),
        (
            "staff_client",
            [
                ('Home', 'http://dataworkspace.test:8000/'),
                ("Tools", "/tools/"),
                ('About', '/about/'),
                (
                    'Help centre',
                    'https://data-services-help.trade.gov.uk/data-workspace',
                ),
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
            ],
        ),
    ),
    indirect=["request_client"],
)
def test_footer_links(request_client, expected_links):
    response = request_client.get(reverse("root"))

    soup = BeautifulSoup(response.content.decode(response.charset))
    footer_links = soup.find("footer").find_all("a")

    link_labels = [
        (link.get_text(strip=True), link.get('href')) for link in footer_links
    ]

    assert link_labels == expected_links
