import json

import psycopg2
import pytest
from django.conf import settings
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework import status

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import (
    DataGrouping,
    DataSet,
    ReferenceDataset,
    SourceTable,
)
from dataworkspace.tests import factories
from dataworkspace.tests.api_v1.base import BaseAPIViewTest
from dataworkspace.apps.datasets.constants import DataSetType


def flush_database(connection):
    connection.autocommit = True
    with connection.cursor() as cursor:
        sql = "select current_user"
        cursor.execute(sql)
        current_user = cursor.fetchone()[0]
        sql = "DROP SCHEMA IF EXISTS public CASCADE;"
        cursor.execute(sql)
        sql = "CREATE SCHEMA public;"
        cursor.execute(sql)
        sql = "GRANT ALL ON SCHEMA public TO {};".format(current_user)
        cursor.execute(sql)
        sql = "GRANT ALL ON SCHEMA public TO {};".format(current_user)
        cursor.execute(sql)


class TestAPIDatasetView(TestCase):
    def flush_database(self):
        with psycopg2.connect(database_dsn(settings.DATABASES_DATA[self.memorable_name])) as conn:
            flush_database(conn)

    def setUp(self):
        self.table = "test_source_table"
        self.memorable_name = "test_external_db"
        self.flush_database()

    def tearDown(self):
        self.flush_database()

    def test_route(self):
        url = "/api/v1/dataset/future-interest-countries/table-id"
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "api-v1:dataset:api-dataset-view")

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
            sql = """
            create table {table} (id int primary key, name varchar(100), timestamp timestamp)
            """.format(
                table=table
            )
            cur.execute(sql)
            sql = """insert into {table} values (%s, %s, %s)""".format(table=self.table)
            values = [
                (0, "abigail", "2019-01-01 01:00"),
                (1, "romeo", "2019-01-01 02:00"),
            ]
            cur.executemany(sql, values)

        url = "/api/v1/dataset/{}/{}".format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {
            "headers": ["id", "name", "timestamp"],
            "next": None,
            "values": [
                [0, "abigail", "2019-01-01 01:00:00"],
                [1, "romeo", "2019-01-01 02:00:00"],
            ],
        }

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode("utf-8"))
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
            sql = """
            create table {table} (id int primary key, name varchar(100), timestamp timestamp)
            """.format(
                table=table
            )
            cur.execute(sql)

        url = "/api/v1/dataset/{}/{}".format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {"headers": ["id", "name", "timestamp"], "next": None, "values": []}

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode("utf-8"))
        self.assertEqual(output_dict, expected)

    def test_friendly_exception_from_non_standard_table(self):
        # create django objects
        memorable_name = self.memorable_name
        table = self.table
        database = Database.objects.get_or_create(memorable_name=memorable_name)[0]
        data_grouping = DataGrouping.objects.get_or_create()[0]
        dataset = DataSet.objects.get_or_create(grouping=data_grouping)[0]
        _ = SourceTable.objects.get_or_create(dataset=dataset, database=database, table=table)[0]
        view_source_table = SourceTable.objects.get_or_create(
            dataset=dataset, database=database, table=f"view_{table}"
        )[0]

        # create external source table
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[memorable_name])
        ) as conn, conn.cursor() as cur:
            sql = """
            create table {table} (id int primary key, name varchar(100), timestamp timestamp)
            """.format(
                table=table
            )
            cur.execute(sql)
            sql = """
            create view view_{table} as (select * from {table})
            """.format(
                table=table
            )
            cur.execute(sql)

        url = "/api/v1/dataset/{}/{}".format(dataset.id, view_source_table.id)
        with pytest.raises(ValueError) as e:
            self.client.get(url)

        assert str(e.value) == (
            "Cannot get primary keys from something other than an ordinary table. "
            "`public`.`view_test_source_table` is a: view"
        )

    def test_friendly_exception_from_table_without_primary_key(self):
        """This test is in place to assert existing behaviour. It may well be reasonable to make this view work
        without primary keys on the table."""
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
            sql = """
            create table {table} (id int, name varchar(100), timestamp timestamp)
            """.format(
                table=table
            )
            cur.execute(sql)

        url = "/api/v1/dataset/{}/{}".format(dataset.id, source_table.id)
        with pytest.raises(ValueError) as e:
            self.client.get(url)

        assert str(e.value) == (
            f"Cannot order response without a primary key on the table: "
            f"`{source_table.schema}`.`{source_table.table}`"
        )

    def test_friendly_exception_from_non_existent_table(self):
        """This test is in place to assert existing behaviour. It may well be reasonable to make this view work
        without primary keys on the table."""
        # create django objects
        memorable_name = self.memorable_name
        table = self.table
        database = Database.objects.get_or_create(memorable_name=memorable_name)[0]
        data_grouping = DataGrouping.objects.get_or_create()[0]
        dataset = DataSet.objects.get_or_create(grouping=data_grouping)[0]
        source_table = SourceTable.objects.get_or_create(
            dataset=dataset, database=database, table=table
        )[0]

        url = "/api/v1/dataset/{}/{}".format(dataset.id, source_table.id)
        with pytest.raises(ValueError) as e:
            self.client.get(url)

        assert str(e.value) == (
            f"Table does not exist: `{source_table.schema}`.`{source_table.table}`"
        )

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
            sql = """
            create table {table} (id int primary key, name varchar(100))
            """.format(
                table=table
            )
            cur.execute(sql)
            sql = """insert into {table} values (%s, %s)""".format(table=self.table)
            values = [(0, "abigail"), (1, "romeo")]
            cur.executemany(sql, values)

        url = "/api/v1/dataset/{}/{}?$searchAfter=0".format(dataset.id, source_table.id)
        response = self.client.get(url)
        expected = {"headers": ["id", "name"], "values": [[1, "romeo"]], "next": None}

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output
        output_dict = json.loads(output.decode("utf-8"))
        self.assertEqual(output_dict, expected)


class TestAPIReferenceDatasetView(TestCase):
    def test_route(self):
        url = "/api/v1/reference-dataset/testgroup/reference/test"
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "api-v1:reference-dataset:api-reference-dataset-view")

    def test_get_data_linked_reference_table(self):
        group = factories.DataGroupingFactory.create()
        linked_rds = factories.ReferenceDatasetFactory.create(
            group=group, table_name="test_get_ref_data_linked"
        )
        linked_field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name="id", data_type=2, is_identifier=True
        )
        linked_field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_rds, name="name", data_type=1
        )
        rds = factories.ReferenceDatasetFactory.create(group=group, table_name="test_get_ref_data")
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="linked: id",
            relationship_name="rel_1",
            data_type=8,
            linked_reference_dataset_field=linked_field1,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="linked: name",
            relationship_name="rel_1",
            data_type=8,
            linked_reference_dataset_field=linked_field2,
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds,
            name="auto uuid",
            column_name="auto_uuid",
            data_type=9,
            sort_order=4,
        )
        link_record = linked_rds.save_record(
            None,
            {
                "reference_dataset": linked_rds,
                linked_field1.column_name: 1,
                linked_field2.column_name: "Linked Display Name",
            },
        )
        rec1 = rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 1,
                field2.column_name: "Test record",
                "rel_1": link_record,
            },
        )
        rec2 = rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 2,
                field2.column_name: "Ánd again",
                "rel_1": None,
            },
        )

        url = f"/api/v1/reference-dataset/{group.slug}/reference/{rds.slug}"
        response = self.client.get(url)

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(output.decode("utf-8")),
            {
                "headers": ["auto uuid", "id", "linked: id", "linked: name", "name"],
                "values": [
                    [str(rec1.auto_uuid), 1, 1, "Linked Display Name", "Test record"],
                    [str(rec2.auto_uuid), 2, None, None, "Ánd again"],
                ],
                "next": None,
            },
        )

    def test_get_data_empty_table(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(
            group=group, table_name="test_get_empty_ref_data"
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1
        )

        url = f"/api/v1/reference-dataset/{group.slug}/reference/{rds.slug}"
        response = self.client.get(url)

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(output.decode("utf-8")),
            {"headers": ["id", "name"], "values": [], "next": None},
        )

    def test_get_data_search_after(self):
        group = factories.DataGroupingFactory.create()
        rds = factories.ReferenceDatasetFactory.create(
            group=group, table_name="test_get_ref_data_search_after"
        )
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1
        )
        rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 1,
                field2.column_name: "Test record",
            },
        )
        rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 2,
                field2.column_name: "Ánd again",
            },
        )

        url = f"/api/v1/reference-dataset/{group.slug}/reference/{rds.slug}?$searchAfter=1"
        response = self.client.get(url)

        output = b""
        for streaming_output in response.streaming_content:
            output = output + streaming_output

        self.assertEqual(
            json.loads(output.decode("utf-8")),
            {"headers": ["id", "name"], "values": [[2, "Ánd again"]], "next": None},
        )


@pytest.mark.django_db
class TestCatalogueItemsAPIView(BaseAPIViewTest):
    url = reverse("api-v1:dataset:catalogue-items")
    factory = factories.DataSetFactory
    pagination_class = "dataworkspace.apps.api_v1.datasets.views.PageNumberPagination.page_size"

    def expected_response(
        self,
        dataset,
        purpose,
        personal_data=None,
        retention_policy=None,
        eligibility_criteria=None,
    ):
        return {
            "id": str(dataset.uuid) if isinstance(dataset, ReferenceDataset) else str(dataset.id),
            "name": dataset.name,
            "short_description": dataset.short_description,
            "description": dataset.description or None,
            "published": dataset.published,
            "created_date": dataset.created_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "published_at": dataset.published_at.strftime("%Y-%m-%d")
            if dataset.published_at
            else None,
            "information_asset_owner": dataset.information_asset_owner.id
            if dataset.information_asset_owner
            else None,
            "information_asset_manager": dataset.information_asset_manager.id
            if dataset.information_asset_manager
            else None,
            "enquiries_contact": dataset.enquiries_contact.id
            if dataset.enquiries_contact
            else None,
            "is_draft": dataset.is_draft if dataset.type == DataSetType.REFERENCE else None,
            "dictionary_published": getattr(dataset, "dictionary_published", None),
            "licence": dataset.licence or None,
            "purpose": purpose,
            "source_tags": [t.name for t in dataset.tags.all()] if dataset.tags.all() else None,
            "personal_data": personal_data,
            "retention_policy": retention_policy,
            "eligibility_criteria": list(eligibility_criteria) if eligibility_criteria else None,
            "source_tables": [
                {"id": str(x.id), "name": x.name, "schema": x.schema, "table": x.table}
                for x in dataset.sourcetable_set.all()
            ]
            if dataset.type == DataSetType.MASTER
            else [],
            "slug": dataset.slug,
        }

    def test_success(self, unauthenticated_client):
        datacut = factories.DatacutDataSetFactory(
            information_asset_owner=factories.UserFactory(),
            information_asset_manager=factories.UserFactory(),
            enquiries_contact=factories.UserFactory(),
            personal_data="personal",
            retention_policy="retention",
            eligibility_criteria=["eligibility"],
        )
        datacut.tags.set([factories.SourceTagFactory()])

        master_dataset = factories.MasterDataSetFactory(
            information_asset_owner=factories.UserFactory(),
            information_asset_manager=factories.UserFactory(),
            personal_data="personal",
            retention_policy="retention",
            dictionary_published=True,
        )
        factories.SourceTableFactory(dataset=master_dataset, schema="public", table="test_table1")
        factories.SourceTableFactory(dataset=master_dataset, schema="public", table="test_table1")
        reference_dataset = factories.ReferenceDatasetFactory(
            information_asset_owner=factories.UserFactory(),
        )

        visualisation = factories.VisualisationCatalogueItemFactory(
            personal_data="personal",
        )

        visualisation2 = factories.VisualisationCatalogueItemFactory(published=False)

        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

        assert response.json()["results"] == [
            self.expected_response(
                datacut,
                "Data cut",
                datacut.personal_data,
                datacut.retention_policy,
                datacut.eligibility_criteria,
            ),
            self.expected_response(
                master_dataset,
                "Master dataset",
                master_dataset.personal_data,
                master_dataset.retention_policy,
            ),
            self.expected_response(reference_dataset, "Reference data"),
            # self.expected_response(reference_dataset.reference_dataset_inheriting_from_dataset, "Reference data"),
            self.expected_response(visualisation, "Visualisation", visualisation.personal_data),
            self.expected_response(visualisation2, "Visualisation"),
        ]


@pytest.mark.django_db
class TestToolQueryAuditLogAPIView(BaseAPIViewTest):
    url = reverse("api-v1:dataset:tool-query-audit-logs")
    factory = factories.ToolQueryAuditLogFactory
    pagination_class = "dataworkspace.apps.api_v1.pagination.TimestampCursorPagination.page_size"

    def expected_response(
        self,
        log,
    ):
        return {
            "id": log.id,
            "user": log.user_id,
            "database": log.database.memorable_name,
            "query_sql": log.query_sql[: settings.TOOL_QUERY_LOG_API_QUERY_TRUNC_LENGTH],
            "rolename": log.rolename,
            "timestamp": log.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "tables": [
                {"id": table.id, "schema": table.schema, "table": table.table}
                for table in log.tables.all().order_by("id")
            ],
        }

    def test_success(self, unauthenticated_client):
        log_1 = factories.ToolQueryAuditLogFactory.create()
        log_2 = factories.ToolQueryAuditLogFactory.create()
        factories.ToolQueryAuditLogTableFactory.create(audit_log=log_2)
        factories.ToolQueryAuditLogTableFactory.create(audit_log=log_2)
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == [
            self.expected_response(log_1),
            self.expected_response(log_2),
        ]

    def test_large_query(self, unauthenticated_client):
        chars = settings.TOOL_QUERY_LOG_API_QUERY_TRUNC_LENGTH
        log = factories.ToolQueryAuditLogFactory.create(
            query_sql=f'SELECT {",".join(["X" for _ in range(chars)])} FROM a_table;'
        )
        factories.ToolQueryAuditLogTableFactory.create(audit_log=log)
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == [self.expected_response(log)]
