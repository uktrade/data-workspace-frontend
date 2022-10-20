import pytest

from django.urls import reverse

from dataworkspace.tests.common import get_response_csp_as_set
from dataworkspace.tests.factories import (
    DatacutDataSetFactory,
    MasterDataSetFactory,
    ReferenceDatasetFactory,
)


def test_baseline_content_security_policy(client):
    response = client.get(reverse("datasets:find_datasets"))
    assert response.status_code == 200

    policies = get_response_csp_as_set(response)
    expected_policies = {
        "object-src 'none'",
        "form-action dataworkspace.test:8000 *.dataworkspace.test:8000",
        "base-uri dataworkspace.test:8000",
        "img-src dataworkspace.test:8000 data: https://www.googletagmanager.com https://www.googletagmanager.com https://www.google-analytics.com https://ssl.gstatic.com https://www.gstatic.com *.google-analytics.com *.googletagmanager.com",  # pylint: disable=line-too-long
        f"script-src dataworkspace.test:8000 https://www.googletagmanager.com https://www.google-analytics.com https://tagmanager.google.com *.googletagmanager.com 'nonce-{response.wsgi_request.csp_nonce}'",  # pylint: disable=line-too-long
        "frame-ancestors dataworkspace.test:8000",
        "font-src dataworkspace.test:8000 data: https://fonts.gstatic.com",
        "style-src dataworkspace.test:8000 'unsafe-inline' https://tagmanager.google.com https://fonts.googleapis.com",
        "default-src dataworkspace.test:8000",
        "connect-src dataworkspace.test:8000 https://www.google-analytics.com *.google-analytics.com *.analytics.google.com "
        "*.googletagmanager.com",
    }

    assert policies == expected_policies


@pytest.mark.parametrize(
    "url,factory,unsafe_inline_script",
    (
        ("admin:datasets_referencedataset_add", None, True),
        ("admin:datasets_referencedataset_change", ReferenceDatasetFactory, True),
        ("admin:datasets_masterdataset_add", None, True),
        ("admin:datasets_masterdataset_change", MasterDataSetFactory, True),
        ("admin:datasets_datacutdataset_add", None, True),
        ("admin:datasets_datacutdataset_change", DatacutDataSetFactory, True),
        ("admin:index", None, False),
    ),
)
def test_dataset_admin_pages_allow_inline_scripts_for_ckeditor_support(
    staff_client, url, factory, unsafe_inline_script
):
    args = None
    if factory:
        dataset = factory.create()
        args = (dataset.id,)

    # Log into admin
    staff_client.get(reverse("admin:index"), follow=True)

    full_url = reverse(url, args=args)
    response = staff_client.get(full_url, follow=True)
    script_src = get_csp_section(response, "script-src")
    assert ("'unsafe-inline'" in script_src) is unsafe_inline_script

    style_src = get_csp_section(response, "style-src")
    assert "'unsafe-inline'" in style_src


def get_csp_section(response, policy_type):
    return next(
        filter(
            lambda policy: policy.strip().startswith(policy_type),
            response.get("content-security-policy").split(";"),
        )
    )
