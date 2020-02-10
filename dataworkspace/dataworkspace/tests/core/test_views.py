import mock

from django.urls import reverse

from dataworkspace.tests.common import BaseTestCase


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
