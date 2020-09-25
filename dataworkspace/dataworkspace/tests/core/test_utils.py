import re

import psycopg2
import pytest
from django.conf import settings

from dataworkspace.apps.core.utils import (
    database_dsn,
    get_random_data_sample,
    postgres_user,
)
from dataworkspace.tests import factories


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
