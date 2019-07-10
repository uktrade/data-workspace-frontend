from django.test import TestCase


class BaseTestCase(TestCase):
    def setUp(self):
        self.user_data = {
            'HTTP_SSO_PROFILE_EMAIL': 'bob.testerson@test.com',
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

    def _authenticated_post(self, url, data=None):
        return self.client.post(
            url,
            data=data,
            **self.user_data
        )
