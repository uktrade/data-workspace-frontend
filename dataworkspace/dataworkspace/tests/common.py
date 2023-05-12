import uuid

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase, TestCase
from django.urls import reverse

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.models import get_user_model
from dataworkspace.apps.datasets.models import ReferenceDataset


class BaseTestCaseMixin:
    def setUp(self):
        username = uuid.uuid4()
        self.user = get_user_model().objects.create(
            username=username, is_staff=True, is_superuser=True, email=username
        )

        self.user.user_permissions.add(
            Permission.objects.get(
                codename="start_all_applications",
                content_type=ContentType.objects.get_for_model(ApplicationInstance),
            )
        )
        self.user.profile.sso_id = uuid.uuid4()

        self.user.profile.save()

        self.user_data = {
            "HTTP_SSO_PROFILE_EMAIL": self.user.email,
            "HTTP_SSO_PROFILE_CONTACT_EMAIL": self.user.email,
            "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
            "HTTP_SSO_PROFILE_USER_ID": "aae8901a-082f-4f12-8c6c-fdf4aeba2d68",
            "HTTP_SSO_PROFILE_LAST_NAME": "Bob",
            "HTTP_SSO_PROFILE_FIRST_NAME": "Testerson",
        }

    def _authenticated_get(self, url, params=None):
        return self.client.get(url, data=params, **self.user_data)

    def _authenticated_post(self, url, data=None, post_format=None):
        return self.client.post(url, data=data, follow=True, format=post_format, **self.user_data)

    def _authenticated_put(self, url, data=None):
        return self.client.put(url, data=data, **self.user_data)

    def _create_reference_dataset(self, **kwargs):
        ref_data_fields = dict(
            name="Test Reference Dataset 1",
            table_name="ref_test_dataset",
            short_description="Testing...",
            information_asset_manager=self.user,
            information_asset_owner=self.user,
            slug="test-reference-dataset-1",
            published=True,
        )
        ref_data_fields.update(kwargs)
        return ReferenceDataset.objects.create(**ref_data_fields)


class BaseTestCase(BaseTestCaseMixin, TestCase):
    pass


class BaseTransactionTestCase(BaseTestCaseMixin, TransactionTestCase):
    """
    Uses TransactionTestCase so the tests aren't run within a transaction.atomic block.
    This allows tests that have with transaction.atomic blocks and commit and rollback functionality
    to be tested.

    https://docs.djangoproject.com/en/2.2/topics/testing/tools/#transactiontestcase

    Due to the schema being manipulated by the codebase when reference dataset tables and fields are created
    Tests that create then try to amend this structure can result in the following error:
    `ALTER TABLE "table_name" because it has pending trigger events` using the TransactionTestCase solves this issue.
    """


class BaseAdminTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Authenticate the user on the admin site
        self._authenticated_post(reverse("admin:index"))


def get_response_csp_as_set(response):
    policies = response["Content-Security-Policy"].split(";")
    policies = {policy.strip() for policy in policies}

    return policies


def get_connect_src_from_csp(response):
    policies = response["Content-Security-Policy"].split(";")
    # find the connect-src policy and split out all elements
    connect_src = "connect-src"
    csp = list(filter(lambda p: connect_src in p, policies))[0].strip().split(" ")
    csp.remove(connect_src)

    csp_set = set(csp)

    return csp_set


def get_http_sso_data(user):
    return {
        "HTTP_SSO_PROFILE_EMAIL": user.email,
        "HTTP_SSO_PROFILE_CONTACT_EMAIL": user.email,
        "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
        "HTTP_SSO_PROFILE_USER_ID": user.profile.sso_id,
        "HTTP_SSO_PROFILE_LAST_NAME": user.last_name,
        "HTTP_SSO_PROFILE_FIRST_NAME": user.first_name,
    }


class MatchUnorderedMembers(list):
    def __eq__(self, other):
        return len(self) == len(other) and all(o in self for o in other)
