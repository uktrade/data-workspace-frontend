from django.urls import reverse

from dataworkspace.tests.common import get_response_csp_as_set
from dataworkspace.tests import factories


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


def test_edit_reference_dataset_admin_pages_allow_inline_scripts_for_ckeditor_support(
    staff_client
):
    dataset = factories.ReferenceDatasetFactory.create()

    # Log into admin
    staff_client.get(reverse("admin:index"), follow=True)

    urls = [
        reverse("admin:datasets_referencedataset_add"),
        reverse('admin:datasets_referencedataset_change', args=(dataset.id,)),
    ]
    for url in urls:
        response = staff_client.get(url, follow=True)
        script_src = next(
            filter(
                lambda policy: policy.strip().startswith('script-src'),
                response.get('content-security-policy').split(';'),
            )
        )
        assert "'unsafe-inline'" in script_src
