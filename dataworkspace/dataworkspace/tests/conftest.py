import psycopg2
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
import pytest

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.tests import factories


@pytest.fixture
def staff_user_data(db):
    user = get_user_model().objects.create(
        username='bob.testerson@test.com', is_staff=True, is_superuser=True
    )

    return {
        'HTTP_SSO_PROFILE_EMAIL': user.email,
        'HTTP_SSO_PROFILE_CONTACT_EMAIL': user.email,
        'HTTP_SSO_PROFILE_RELATED_EMAILS': '',
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d68',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Testerson',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Bob',
    }


@pytest.fixture
def staff_client(staff_user_data):
    return Client(**staff_user_data)


@pytest.fixture
def user(db):
    user = get_user_model().objects.create(
        username='frank.exampleson@test.com', is_staff=False, is_superuser=False
    )

    return user


@pytest.fixture
def user_data(db, user):

    return {
        'HTTP_SSO_PROFILE_EMAIL': user.email,
        'HTTP_SSO_PROFILE_CONTACT_EMAIL': user.email,
        'HTTP_SSO_PROFILE_RELATED_EMAILS': '',
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d69',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Exampleson',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Frank',
    }


@pytest.fixture
def client(user_data):
    return Client(**user_data)


@pytest.fixture
def sme_user(db):
    sme_group = Group.objects.get(name="Subject Matter Experts")
    user = get_user_model().objects.create(
        username='jane.sampledóttir@test.com', is_staff=True, is_superuser=False
    )
    sme_group.user_set.add(user)
    sme_group.save()

    return user


@pytest.fixture
def sme_user_data(db, sme_user):
    return {
        'HTTP_SSO_PROFILE_EMAIL': sme_user.email,
        'HTTP_SSO_PROFILE_CONTACT_EMAIL': sme_user.email,
        'HTTP_SSO_PROFILE_RELATED_EMAILS': '',
        'HTTP_SSO_PROFILE_USER_ID': 'aae8901a-082f-4f12-8c6c-fdf4aeba2d70',
        'HTTP_SSO_PROFILE_LAST_NAME': 'Sampledóttir',
        'HTTP_SSO_PROFILE_FIRST_NAME': 'Jane',
    }


@pytest.fixture
def sme_client(sme_user, sme_user_data):
    client = Client(**sme_user_data)
    client.force_login(sme_user)
    return client


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


@pytest.fixture
def metadata_db(db):
    database = factories.DatabaseFactory(memorable_name='my_database')
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA['my_database'])
    ) as conn, conn.cursor() as cursor:
        cursor.execute(
            '''
            CREATE SCHEMA IF NOT EXISTS dataflow;
            CREATE TABLE IF NOT EXISTS dataflow.metadata (
                id int, table_schema text, table_name text, source_data_modified_utc timestamp
            );
            TRUNCATE TABLE dataflow.metadata;
            INSERT INTO dataflow.metadata VALUES(1, 'public', 'table1', '2020-09-02 00:01:00.0');
            INSERT INTO dataflow.metadata VALUES(1, 'public', 'table2', '2020-09-01 00:01:00.0');
            INSERT INTO dataflow.metadata VALUES(1, 'public', 'table1', '2020-01-01 00:01:00.0');
            INSERT INTO dataflow.metadata VALUES(1, 'public', 'table4', NULL);
            '''
        )
        conn.commit()
    return database
