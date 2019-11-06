import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase


@pytest.fixture
def staff_user_data(db):
    user = User.objects.create(
        username='bob.testerson@test.com', is_staff=True, is_superuser=True
    )

    return {
        'HTTP_SSO_PROFILE_EMAIL': user.email,
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d68',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Bob',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Testerson',
    }


@pytest.fixture
def client(staff_user_data):
    return Client(**staff_user_data)


@pytest.fixture(scope='session')
def test_case():
    return TestCase('run')
