from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='bob.testerson@test.com',
            is_staff=True,
            is_superuser=True
        )

        self.user_data = {
            'HTTP_SSO_PROFILE_EMAIL': self.user.email,
            'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d68',
            'HTTP_SSO_PROFILE_LAST_NAME': 'Bob',
            'HTTP_SSO_PROFILE_FIRST_NAME': 'Testerson'
        }

    def _authenticated_get(self, url, params=None):
        return self.client.get(
            url,
            data=params,
            **self.user_data
        )

    def _authenticated_post(self, url, data=None, post_format=None):
        return self.client.post(
            url,
            data=data,
            follow=True,
            format=post_format,
            **self.user_data,
        )


class BaseAdminTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Authenticate the user on the admin site
        self._authenticated_post(reverse('admin:index'))
