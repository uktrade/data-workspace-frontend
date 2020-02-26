from django.urls import reverse

from dataworkspace.tests.common import get_response_csp_as_set


def test_baseline_content_security_policy(client):
    response = client.get(reverse('datasets:find_datasets'))
    assert response.status_code == 200

    policies = get_response_csp_as_set(response)
    expected_policies = {
        "object-src 'none'",
        "form-action dataworkspace.test:8000 *.dataworkspace.test:8000",
        "base-uri dataworkspace.test:8000",
        "img-src dataworkspace.test:8000 data: https://www.googletagmanager.com https://www.googletagmanager.com https://www.google-analytics.com https://ssl.gstatic.com https://www.gstatic.com",
        f"script-src dataworkspace.test:8000 https://www.googletagmanager.com https://www.google-analytics.com https://tagmanager.google.com 'nonce-{response.wsgi_request.csp_nonce}'",
        "frame-ancestors dataworkspace.test:8000",
        "font-src dataworkspace.test:8000 data: https://fonts.gstatic.com",
        "style-src dataworkspace.test:8000 'unsafe-inline' https://tagmanager.google.com https://fonts.googleapis.com",
        "default-src dataworkspace.test:8000",
    }

    assert policies == expected_policies
