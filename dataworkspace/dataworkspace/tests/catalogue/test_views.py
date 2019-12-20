import pytest
import psycopg2
from django.conf import settings

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.tests import factories


@pytest.fixture
def dataset_db():
    database = factories.DatabaseFactory(memorable_name='my_database')
    with psycopg2.connect(database_dsn(settings.DATABASES_DATA['my_database'])) as conn:
        conn.cursor().execute(
            '''
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
            '''
        )

    return database


def test_master_dataset_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceTableFactory(
        dataset=ds,
        name='d1',
        database=dataset_db,
        schema='public',
        table='dataset_test',
    )
    factories.SourceTableFactory(
        dataset=ds,
        name='d2',
        database=dataset_db,
        schema='public',
        table='dataset_test2',
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == [
        'dataset_test.id',
        'dataset_test.name',
        'dataset_test.date',
        'dataset_test2.id',
        'dataset_test2.name',
    ]


def test_view_data_cut_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceViewFactory(
        dataset=ds, database=dataset_db, schema='public', view='dataset_view'
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == ['id', 'name', 'date']


def test_query_data_cut_fields(client, dataset_db):
    ds = factories.DataSetFactory.create(published=True)
    factories.CustomDatasetQueryFactory(
        dataset=ds,
        database=dataset_db,
        query="SELECT id customid, name customname FROM dataset_test",
    )

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] == ['customid', 'customname']


def test_link_data_cut_doesnt_have_fields(client):
    ds = factories.DataSetFactory.create(published=True)
    factories.SourceLinkFactory(dataset=ds)

    response = client.get(ds.get_absolute_url())

    assert response.status_code == 200
    assert response.context["fields"] is None
