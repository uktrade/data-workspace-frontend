import pytest

from django.urls import reverse

from dataworkspace.apps.datasets.constants import DataSetType
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


@pytest.mark.parametrize(
    'url,unsafe_inline_script',
    (
        ('admin:datasets_referencedataset_add', True),
        ('admin:datasets_referencedataset_change', True),
        ('admin:datasets_masterdataset_add', True),
        ('admin:datasets_masterdataset_change', True),
        ('admin:datasets_datacutdataset_add', True),
        ('admin:datasets_datacutdataset_change', True),
        ('admin:index', False),
    ),
)
def test_dataset_admin_pages_allow_inline_scripts_for_ckeditor_support(
    staff_client, url, unsafe_inline_script
):
    args = None
    if 'change' in url:
        if 'reference' in url:
            dataset = factories.ReferenceDatasetFactory.create()
        elif 'datacut' in url:
            dataset = factories.DataSetFactory.create()
        else:
            dataset = factories.DataSetFactory.create(type=DataSetType.MASTER.value)
        args = (dataset.id,)

    # Log into admin
    staff_client.get(reverse("admin:index"), follow=True)

    full_url = reverse(url, args=args)
    response = staff_client.get(full_url, follow=True)
    script_src = get_src(response, 'script-src')
    assert ("'unsafe-inline'" in script_src) is unsafe_inline_script

    style_src = get_src(response, 'style-src')
    assert "'unsafe-inline'" in style_src


def get_src(response, policy_type):
    return next(
        filter(
            lambda policy: policy.strip().startswith(policy_type),
            response.get('content-security-policy').split(';'),
        )
    )
