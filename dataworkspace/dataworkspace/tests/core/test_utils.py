import psycopg2
import pytest
from django.conf import settings

from dataworkspace.apps.core.utils import database_dsn, get_random_data_sample
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
