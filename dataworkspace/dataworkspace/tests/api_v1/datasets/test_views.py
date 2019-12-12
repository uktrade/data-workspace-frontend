import json
import psycopg2
from django.test import TestCase
from django.urls import resolve
from django.conf import settings
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import DataGrouping, DataSet, SourceTable


def flush_database(connection):
    connection.autocommit = True
    with connection.cursor() as cursor:
        sql = 'select current_user'
        cursor.execute(sql)
        current_user = cursor.fetchone()[0]
        sql = 'DROP SCHEMA IF EXISTS public CASCADE;'
        cursor.execute(sql)
        sql = 'CREATE SCHEMA public;'
        cursor.execute(sql)
        sql = 'GRANT ALL ON SCHEMA public TO {};'.format(current_user)
        cursor.execute(sql)
        sql = 'GRANT ALL ON SCHEMA public TO {};'.format(current_user)
        cursor.execute(sql)


class TestAPIDatasetView(TestCase):
    def flush_database(self):
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[self.memorable_name])
        ) as conn:
            flush_database(conn)

    def setUp(self):
        self.table = 'test_source_table'
        self.memorable_name = 'test_external_db'
        self.flush_database()

    def tearDown(self):
        self.flush_database()

    def test_route(self):
        url = '/api/v1/dataset/future-interest-countries/table-id'
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, 'api-v1:dataset:api-dataset-view')

    def test_data(self):

        # create django objects
        memorable_name = self.memorable_name
        table = self.table
        database = Database.objects.get_or_create(memorable_name=memorable_name)[0]
        data_grouping = DataGrouping.objects.get_or_create()[0]
        dataset = DataSet.objects.get_or_create(grouping=data_grouping)[0]
        source_table = SourceTable.objects.get_or_create(
            dataset=dataset, database=database, table=table
        )[0]

        # create external source table
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[memorable_name])
        ) as conn, conn.cursor() as cur:
            sql = '''
            create table {table} (id int primary key, name varchar(100), timestamp timestamp)
            '''.format(
                table=table
            )
            cur.execute(sql)
            sql = '''insert into {table} values (%s, %s, %s)'''.format(table=self.table)
            values = [
                (0, 'abigail', '2019-01-01 01:00'),
                (1, 'romeo', '2019-01-01 02:00'),
            ]
            cur.executemany(sql, values)

        url = '/api/v1/dataset/{}/{}'.format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {
            'headers': ['id', 'name', 'timestamp'],
            'next': None,
            'values': [
                [0, 'abigail', '2019-01-01 01:00:00'],
                [1, 'romeo', '2019-01-01 02:00:00'],
            ],
        }

        output = b''
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode('utf-8'))
        self.assertEqual(output_dict, expected)

    def test_empty_data(self):

        # create django objects
        memorable_name = self.memorable_name
        table = self.table
        database = Database.objects.get_or_create(memorable_name=memorable_name)[0]
        data_grouping = DataGrouping.objects.get_or_create()[0]
        dataset = DataSet.objects.get_or_create(grouping=data_grouping)[0]
        source_table = SourceTable.objects.get_or_create(
            dataset=dataset, database=database, table=table
        )[0]

        # create external source table
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[memorable_name])
        ) as conn, conn.cursor() as cur:
            sql = '''
            create table {table} (id int primary key, name varchar(100), timestamp timestamp)
            '''.format(
                table=table
            )
            cur.execute(sql)

        url = '/api/v1/dataset/{}/{}'.format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {'headers': ['id', 'name', 'timestamp'], 'next': None, 'values': []}

        output = b''
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode('utf-8'))
        self.assertEqual(output_dict, expected)

    def test_search_after(self):

        # create django objects
        memorable_name = self.memorable_name
        table = self.table
        database = Database.objects.get_or_create(memorable_name=memorable_name)[0]
        data_grouping = DataGrouping.objects.get_or_create()[0]
        dataset = DataSet.objects.get_or_create(grouping=data_grouping)[0]
        source_table = SourceTable.objects.get_or_create(
            dataset=dataset, database=database, table=table
        )[0]

        # create external source table
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[memorable_name])
        ) as conn, conn.cursor() as cur:
            sql = '''
            create table {table} (id int primary key, name varchar(100))
            '''.format(
                table=table
            )
            cur.execute(sql)
            sql = '''insert into {table} values (%s, %s)'''.format(table=self.table)
            values = [(0, 'abigail'), (1, 'romeo')]
            cur.executemany(sql, values)

        url = '/api/v1/dataset/{}/{}?$searchAfter=0'.format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {'headers': ['id', 'name'], 'values': [[1, 'romeo']], 'next': None}

        output = b''
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode('utf-8'))
        self.assertEqual(output_dict, expected)
