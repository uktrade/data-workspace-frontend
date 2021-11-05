import datetime
import re
import time

import mock
import psycopg2
import pytest
from django.conf import settings
from django.db import connections
from django.test import override_settings

from dataworkspace.apps.applications.utils import delete_unused_datasets_users
from dataworkspace.apps.core.models import DatabaseUser
from dataworkspace.apps.core.utils import (
    database_dsn,
    get_random_data_sample,
    postgres_user,
    source_tables_for_user,
    db_role_schema_suffix_for_user,
    new_private_database_credentials,
)
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.management.commands.ensure_databases_configured import (
    Command as ensure_databases_configured,
)
from dataworkspace.tests import factories
from dataworkspace.tests.factories import (
    UserFactory,
    SourceTableFactory,
    MasterDataSetFactory,
)


class TestGetRandomSample:
    @pytest.fixture
    def test_db(self, db):
        database = factories.DatabaseFactory(memorable_name='my_database')
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA['my_database'])
        ) as conn:
            conn.cursor().execute(
                '''
            CREATE TABLE IF NOT EXISTS test_sample AS (
                with data (x, y, z) as (values
                    (NULL, NULL, NULL),
                    ('a', 'b', 'c'),
                    ('a', 'b', NULL),
                    ('a', NULL, NULL)
                )
                SELECT * from data
            );
            '''
            )
            conn.commit()
            yield database.memorable_name
            conn.cursor().execute('DROP TABLE test_sample')

    def test_get_sample_prefers_less_none(self, test_db):
        query = 'select * from test_sample'
        sample = get_random_data_sample(test_db, query, sample_size=2)
        assert ('a', 'b', 'c') in sample
        assert ('a', 'b', None) in sample
        assert len(sample) == 2

    def test_get_sample_bigger_then_dataset(self, test_db):
        query = 'select * from test_sample'
        sample = get_random_data_sample(test_db, query, sample_size=20)
        assert ('a', 'b', 'c') in sample
        assert ('a', 'b', None) in sample
        assert ('a', None, None) in sample
        assert (None, None, None) in sample
        assert len(sample) == 4


class TestPostgresUser:
    def test_very_long_suffix_raises_value_error(self):
        with pytest.raises(ValueError):
            postgres_user(
                'short@email.com',
                suffix='my-very-long-suffix-that-uses-too-many-characters',
            )

    @pytest.mark.parametrize(
        'email, suffix, expected_match, expected_length',
        (
            ('short@email.com', '', r'^user_short_email_com_[a-z0-9]{5}$', 26),
            (
                'a.silly.super.unnecessarily_very.long-email@my.subdomain.domain.com',
                '',
                r'^user_a_silly_super_unnecessarily_very_long_email_my_subdo_[a-z0-9]{5}$',
                63,
            ),
            (
                'a.silly.super.unnecessarily_very.long-email@my.subdomain.domain.com',
                'suffix',
                r'^user_a_silly_super_unnecessarily_very_long_email_m_[a-z0-9]{5}_suffix$',
                63,
            ),
        ),
    )
    def test_postgres_user_is_restricted_to_63_chars(
        self, email, suffix, expected_match, expected_length
    ):
        username = postgres_user(email, suffix=suffix)
        assert re.match(expected_match, username)
        assert len(username) == expected_length

    @pytest.mark.django_db(transaction=True)
    def test_db_user_record(self):
        user_count = DatabaseUser.objects.count()

        user = factories.UserFactory()
        source_tables = source_tables_for_user(user)
        db_role_schema_suffix = db_role_schema_suffix_for_user(user)
        new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            user.email,
            user,
            valid_for=datetime.timedelta(days=31),
        )
        assert DatabaseUser.objects.count() == user_count + 1


class TestNewPrivateDatabaseCredentials:
    @pytest.mark.django_db(transaction=True)
    @override_settings(PGAUDIT_LOG_SCOPES='ALL')
    def test_new_credentials_have_pgaudit_configuration(self):
        ensure_databases_configured().handle()

        user = UserFactory(email='test@foo.bar')
        st = SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type=UserAccessType.REQUIRES_AUTHENTICATION
            )
        )

        source_tables = source_tables_for_user(user)
        db_role_schema_suffix = db_role_schema_suffix_for_user(user)
        user_creds_to_drop = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email),
            user,
            valid_for=datetime.timedelta(days=1),
        )

        connections[st.database.memorable_name].cursor().execute('COMMIT')

        rolename = user_creds_to_drop[0]['db_user']
        query = f"SELECT rolname, rolconfig FROM pg_roles WHERE rolname = '{rolename}';"

        with connections[st.database.memorable_name].cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            assert 'pgaudit.log=ALL' in results[0][1]
            assert 'pgaudit.log_catalog=off' in results[0][1]


class TestDeleteUnusedDatasetsUsers:
    @pytest.mark.django_db(transaction=True)
    def test_deletes_expired_and_unused_users(self):
        ensure_databases_configured().handle()

        user = UserFactory(email='test@foo.bar')
        st = SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        source_tables = source_tables_for_user(user)
        db_role_schema_suffix = db_role_schema_suffix_for_user(user)
        user_creds_to_drop = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email),
            user,
            valid_for=datetime.timedelta(days=31),
        )
        qs_creds_to_drop = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email, suffix='qs'),
            user,
            valid_for=datetime.timedelta(seconds=0),
        )
        qs_creds_to_keep = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email, suffix='qs'),
            user,
            valid_for=datetime.timedelta(minutes=1),
        )

        connections[st.database.memorable_name].cursor().execute('COMMIT')

        # Make sure that `qs_creds_to_drop` has definitely expired
        time.sleep(1)

        with mock.patch('dataworkspace.apps.applications.utils.gevent.sleep'):
            delete_unused_datasets_users()

        with connections[st.database.memorable_name].cursor() as cursor:
            cursor.execute(
                "SELECT usename FROM pg_catalog.pg_user WHERE usename IN %s",
                [
                    (
                        user_creds_to_drop[0]['db_user'],
                        qs_creds_to_drop[0]['db_user'],
                        qs_creds_to_keep[0]['db_user'],
                    )
                ],
            )
            assert cursor.fetchall() == [(qs_creds_to_keep[0]['db_user'],)]
