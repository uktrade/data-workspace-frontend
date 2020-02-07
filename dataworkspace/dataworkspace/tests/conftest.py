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
        'HTTP_SSO_PROFILE_RELATED_EMAILS': '',
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d68',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Testerson',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Bob',
    }


@pytest.fixture
def staff_client(staff_user_data):
    return Client(**staff_user_data)


@pytest.fixture
def user_data(db):
    user = User.objects.create(
        username='frank.exampleson@test.com', is_staff=False, is_superuser=False
    )

    return {
        'HTTP_SSO_PROFILE_EMAIL': user.email,
        'HTTP_SSO_PROFILE_RELATED_EMAILS': '',
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d69',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Exampleson',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Frank',
    }


@pytest.fixture
def client(user_data):
    return Client(**user_data)


@pytest.fixture
def unauthenticated_client():
    return Client()


@pytest.fixture
def request_client(request):
    """
    Allows for passing a fixture name to parameterize to return a named fixture
    """
    return request.getfixturevalue(request.param)


@pytest.fixture(scope='session')
def test_case():
    return TestCase('run')
