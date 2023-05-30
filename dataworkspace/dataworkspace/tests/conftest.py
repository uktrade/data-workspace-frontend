import psycopg2
import pytest

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.tests import factories

from dataworkspace.cel import celery_app


@pytest.fixture
def staff_user(db):
    staff_user = factories.UserFactory.create(
        username="aae8901a-082f-4f12-8c6c-fdf4aeba2d68",
        email="bob.testerson@test.com",
        is_staff=True,
        is_superuser=True,
        first_name="Bob",
    )
    staff_user.profile.sso_id = "aae8901a-082f-4f12-8c6c-fdf4aeba2d68"
    staff_user.profile.save()
    return staff_user


def get_user_data(staff_user):
    return {
        "HTTP_SSO_PROFILE_EMAIL": staff_user.email,
        "HTTP_SSO_PROFILE_CONTACT_EMAIL": staff_user.email,
        "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
        "HTTP_SSO_PROFILE_USER_ID": staff_user.username,
        "HTTP_SSO_PROFILE_LAST_NAME": "Testerson",
        "HTTP_SSO_PROFILE_FIRST_NAME": "Bob",
    }


@pytest.fixture
def staff_user_data(db, staff_user):
    return get_user_data(staff_user)


def get_client(data):
    return Client(**data)


@pytest.fixture
def staff_client(staff_user_data):
    return get_client(staff_user_data)


@pytest.fixture
def user(db):
    user = factories.UserFactory.create(
        username="72ccde8c-11a2-432d-9cdb-9b757cd75747",
        is_staff=False,
        is_superuser=False,
        email="frank.exampleson@test.com",
        first_name="Frank",
    )

    return user


@pytest.fixture
def user_data(db, user):
    return {
        "HTTP_SSO_PROFILE_EMAIL": user.email,
        "HTTP_SSO_PROFILE_CONTACT_EMAIL": user.email,
        "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
        "HTTP_SSO_PROFILE_USER_ID": user.username,
        "HTTP_SSO_PROFILE_LAST_NAME": "Exampleson",
        "HTTP_SSO_PROFILE_FIRST_NAME": "Frank",
    }


@pytest.fixture
def client(user_data):
    return Client(**user_data)


@pytest.fixture
def sme_user(db):
    sme_group = Group.objects.get(name="Subject Matter Experts")
    user = factories.UserFactory.create(
        username="e9fbe860-f95d-4d2e-98b9-fa125e5d82b0",
        email="jane.sampledóttir@test.com",
        is_staff=True,
        is_superuser=False,
    )
    sme_group.user_set.add(user)
    sme_group.save()

    return user


@pytest.fixture
def sme_user_data(db, sme_user):
    return {
        "HTTP_SSO_PROFILE_EMAIL": sme_user.email,
        "HTTP_SSO_PROFILE_CONTACT_EMAIL": sme_user.email,
        "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
        "HTTP_SSO_PROFILE_USER_ID": sme_user.username,
        "HTTP_SSO_PROFILE_LAST_NAME": "Sampledóttir",
        "HTTP_SSO_PROFILE_FIRST_NAME": "Jane",
    }


@pytest.fixture
def sme_client(sme_user, sme_user_data):
    client = Client(**sme_user_data)
    client.force_login(sme_user)
    return client


@pytest.fixture
def other_user(db):
    return factories.UserFactory.create(
        username="1ece7d19-7749-488e-9a76-3bdac376dce9",
        email="other@test.com",
        is_staff=True,
        is_superuser=False,
    )


@pytest.fixture
def other_user_data(db, other_user):
    return {
        "HTTP_SSO_PROFILE_EMAIL": other_user.email,
        "HTTP_SSO_PROFILE_CONTACT_EMAIL": other_user.email,
        "HTTP_SSO_PROFILE_RELATED_EMAILS": "",
        "HTTP_SSO_PROFILE_USER_ID": other_user.username,
        "HTTP_SSO_PROFILE_LAST_NAME": "Mary",
        "HTTP_SSO_PROFILE_FIRST_NAME": "Poppins",
    }


@pytest.fixture
def other_user_client(other_user, other_user_data):
    client = Client(**other_user_data)
    client.force_login(other_user)
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


@pytest.fixture(scope="session")
def test_case():
    return TestCase("run")


@pytest.fixture
def metadata_db(db):
    database = factories.DatabaseFactory(memorable_name="my_database")
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA["my_database"])
    ) as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE SCHEMA IF NOT EXISTS dataflow;
            CREATE TABLE IF NOT EXISTS dataflow.metadata (
                id SERIAL,
                table_schema TEXT,
                table_name TEXT,
                source_data_modified_utc TIMESTAMP WITHOUT TIME ZONE,
                dataflow_swapped_tables_utc TIMESTAMP WITHOUT TIME ZONE,
                table_structure JSONB,
                data_ids TEXT[],
                data_type INTEGER NOT NULL,
                data_hash_v1 TEXT,
                primary_keys TEXT[],
                number_of_rows INTEGER
            );
            TRUNCATE TABLE dataflow.metadata;
            INSERT INTO dataflow.metadata (
                table_schema, table_name, source_data_modified_utc, dataflow_swapped_tables_utc, table_structure, data_type
            )
            VALUES
                ('public','table1','2020-09-02 00:01:00.0','2020-09-02 00:01:00.0','{"field1":"int","field2":"varchar"}',1),
                ('public','table2','2020-09-01 00:01:00.0','2020-09-02 00:01:00.0',NULL,1),
                ('public','table1','2020-01-01 00:01:00.0','2020-09-02 00:01:00.0',NULL,1),
                ('public','table4', NULL,'2021-12-01 00:00:00.0',NULL,1);
            """
        )
        conn.commit()
    return database


@pytest.fixture
def test_dataset(db):
    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA["my_database"])
    ) as conn, conn.cursor() as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS foo AS SELECT a,b FROM (VALUES ('test',30)) AS temp_table(a,b);"
        )
        cursor.execute(
            """
            CREATE SCHEMA IF NOT EXISTS dataflow;
            CREATE TABLE IF NOT EXISTS dataflow.metadata (
                id SERIAL,
                table_schema TEXT,
                table_name TEXT,
                source_data_modified_utc TIMESTAMP WITHOUT TIME ZONE,
                dataflow_swapped_tables_utc TIMESTAMP WITHOUT TIME ZONE,
                table_structure JSONB,
                data_ids TEXT[],
                data_type INTEGER NOT NULL,
                data_hash_v1 TEXT
            );
            TRUNCATE TABLE dataflow.metadata;
            INSERT INTO dataflow.metadata (table_schema, table_name, source_data_modified_utc, table_structure, data_type)
            VALUES
            ('public', 'foo', '2021-01-01 00:00:00.0', '{"a":"text","b":"int"}', 1);
            """
        )
        conn.commit()
    return ("public", "foo")


@pytest.fixture(autouse=True, scope="session")
def change_staticfiles_storage():
    """
    Slightly strange, but Django recommends not using the manifest
    staticfiles storage when testing because it generates the manifest from
    the `collectstatic` command, which isn't run for tests, so staticfile
    lookup will fail:

    https://docs.djangoproject.com/en/3.1/ref/contrib/staticfiles/#django.contrib.staticfiles.storage.ManifestStaticFilesStorage.manifest_strict
    """
    with override_settings(
        STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def make_celery_eager():
    celery_app.conf.task_always_eager = True


@pytest.fixture
def dataset_db(metadata_db):
    database = factories.DatabaseFactory(memorable_name="my_database")
    with psycopg2.connect(database_dsn(settings.DATABASES_DATA["my_database"])) as conn:
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_test (
                id INT,
                name VARCHAR(255),
                date DATE
            );

            CREATE TABLE IF NOT EXISTS dataset_test2 (
                id INT,
                name VARCHAR(255)
            );

            CREATE OR REPLACE VIEW dataset_view AS (SELECT * FROM dataset_test);
            """
        )

    return database


@pytest.fixture
def dataset_db_with_swap_table(metadata_db):
    database = factories.DatabaseFactory(memorable_name="my_database")
    with psycopg2.connect(database_dsn(settings.DATABASES_DATA["my_database"])) as conn:
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_test (
                id INT,
                name VARCHAR(255),
                date DATE
            );

            DELETE FROM dataset_test;
            INSERT INTO dataset_test values(1,'test','2022-01-01');

            CREATE TABLE IF NOT EXISTS dataset_test_20220101t000000_swap (
                id INT,
                name VARCHAR(255),
                date DATE
            );

            DELETE FROM dataset_test_20220101t000000_swap;
            INSERT INTO dataset_test_20220101t000000_swap values(1,'test','2022-01-01');
            INSERT INTO dataset_test_20220101t000000_swap values(2,'test_2','2022-01-02');

            """
        )

    return database


@pytest.fixture
def dataset_finder_db(metadata_db):
    database = factories.DatabaseFactory(memorable_name="my_database")
    with psycopg2.connect(database_dsn(settings.DATABASES_DATA["my_database"])) as conn:
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS dataworkspace__source_tables (
                id INT,
                name VARCHAR(255),
                dataset_id UUID,
                schema VARCHAR(255),
                "table" VARCHAR(255)
            );

            CREATE TABLE IF NOT EXISTS dataworkspace__catalogue_items (
                id UUID,
                name VARCHAR(255),
                slug VARCHAR(255)
            );

            INSERT INTO dataworkspace__source_tables VALUES(
                1, 'public.data', '0dea6147-d355-4b6d-a140-0304ef9cfeca', 'public', 'data'
            );

            INSERT INTO dataworkspace__catalogue_items VALUES(
                '0dea6147-d355-4b6d-a140-0304ef9cfeca', 'public.data', '1'
            );

            CREATE SCHEMA IF NOT EXISTS public;
            CREATE TABLE IF NOT EXISTS data (
                id int,
                name VARCHAR(255),
                database VARCHAR(255),
                schema VARCHAR(255),
                frequency VARCHAR(255),
                "table" VARCHAR(255)
            );

            CREATE TABLE IF NOT EXISTS country_stats (
                date DATE,
                driving NUMERIC,
                country VARCHAR(255)
            );
            """
        )

    return database
