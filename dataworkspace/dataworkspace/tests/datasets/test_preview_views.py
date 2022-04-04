import io

import psycopg2
import pytest
from botocore.response import StreamingBody

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from waffle.testutils import override_flag

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.tests import factories


class TestCustomQueryPreviewView:
    @pytest.fixture
    def test_db(self, db):
        yield factories.DatabaseFactory(memorable_name="my_database")

    def test_preview_forbidden_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.DATACUT,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query="SELECT * FROM a_table",
        )
        response = client.get(
            reverse(
                "datasets:dataset_query_preview",
                kwargs={"dataset_uuid": dataset.id, "query_id": query.id},
            )
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_preview_invalid_datacut(self, access_type, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.DATACUT,
            user_access_type=access_type,
        )
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query="SELECT * FROM invalid_table",
        )
        response = client.get(
            reverse(
                "datasets:dataset_query_preview",
                kwargs={"dataset_uuid": dataset.id, "query_id": query.id},
            )
        )
        response_content = response.content.decode(response.charset)
        assert "Data Fields" not in response_content
        assert "No data available" in response_content
        assert "Download" not in response_content

    @override_settings(DATASET_PREVIEW_NUM_OF_ROWS=20)
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_preview_valid_datacut(self, access_type, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.DATACUT,
            user_access_type=access_type,
        )

        # Check if sample data shown correctly
        query1 = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query="SELECT 1 as a, 2 as b",
        )
        response = client.get(
            reverse(
                "datasets:dataset_query_preview",
                kwargs={"dataset_uuid": dataset.id, "query_id": query1.id},
            )
        )
        response_content = response.content.decode(response.charset)
        html = "".join([s.strip() for s in response_content.splitlines() if s.strip()])
        assert response.status_code == 200
        assert "<li>a</li><li>b</li>" in html  # check fields
        assert (
            "<thead>"
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header ref-data-col-">a</th>'
            '<th class="govuk-table__header ref-data-col-">b</th>'
            "</tr>"
            "</thead>"
            "<tbody>"
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">1</td>'
            '<td class="govuk-table__cell">2</td>'
            "</tr>"
            "</tbody>"
        ) in html  # check sample data
        assert "Showing all rows from data." in html
        assert "Download" in html  # check download button available

        # Check if sample limited to 20 random rows if more data available
        preview_rows = settings.DATASET_PREVIEW_NUM_OF_ROWS
        query2 = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query=f"SELECT * FROM generate_series(1, {preview_rows * 2}) as a;",
        )

        response = client.get(
            reverse(
                "datasets:dataset_query_preview",
                kwargs={"dataset_uuid": dataset.id, "query_id": query2.id},
            )
        )
        response_content = response.content.decode(response.charset)
        assert (
            f"Showing <strong>{preview_rows}</strong> random rows from data." in response_content
        )

    def _preview_unreviewed_datacut(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.DATACUT,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            published=True,
        )
        sql = "SELECT 1 as a, 2 as b"
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset, database=test_db, query=sql, reviewed=False
        )
        return client.get(
            reverse(
                "datasets:dataset_query_preview",
                kwargs={"dataset_uuid": dataset.id, "query_id": query.id},
            )
        )

    def test_staff_user_can_preview_unreviewed_datacut(self, staff_client, test_db):
        assert self._preview_unreviewed_datacut(staff_client, test_db).status_code == 200

    def test_normal_user_cannot_preview_unreviewed_datacut(self, client, test_db):
        assert self._preview_unreviewed_datacut(client, test_db).status_code == 403


class TestSourceTablePreviewView:
    @pytest.fixture
    def test_db(self, db):
        database = factories.DatabaseFactory(memorable_name="my_database")
        with psycopg2.connect(database_dsn(settings.DATABASES_DATA["my_database"])) as conn:
            conn.cursor().execute(
                """
                CREATE TABLE IF NOT EXISTS test_table AS (
                    SELECT 1 as a, 2 as b
                );
            """
            )
            conn.commit()
            yield database
            conn.cursor().execute("DROP TABLE test_table")

    def test_preview_forbidden_master_dataset(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.MASTER,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        )
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            name="source_table1",
            database=test_db,
            schema="public",
            table="test_table",
        )
        response = client.get(
            reverse(
                "datasets:dataset_table_preview",
                kwargs={"dataset_uuid": dataset.id, "table_uuid": source_table.id},
            )
        )
        assert response.status_code == 403

    @override_settings(DATASET_PREVIEW_NUM_OF_ROWS=10)
    def test_preview_table(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.MASTER,
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
        )

        # Check if sample data shown correctly
        source_table = factories.SourceTableFactory(
            dataset=dataset,
            name="source_table1",
            database=test_db,
            schema="public",
            table="test_table",
        )
        response = client.get(
            reverse(
                "datasets:dataset_table_preview",
                kwargs={"dataset_uuid": dataset.id, "table_uuid": source_table.id},
            )
        )
        response_content = response.content.decode(response.charset)
        html = "".join([s.strip() for s in response_content.splitlines() if s.strip()])
        assert response.status_code == 200
        assert "<li>a</li><li>b</li>" in html  # check fields
        assert (
            "<thead>"
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header ref-data-col-">a</th>'
            '<th class="govuk-table__header ref-data-col-">b</th>'
            "</tr>"
            "</thead>"
            "<tbody>"
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">1</td>'
            '<td class="govuk-table__cell">2</td>'
            "</tr>"
            "</tbody>"
        ) in html  # check sample data
        assert "Showing all rows from data." in html
        assert "Download" not in html  # check download button available


@pytest.mark.django_db
class TestDataCutPreviewDownloadView:
    @pytest.fixture
    def test_db(self, db):
        database = factories.DatabaseFactory(memorable_name="my_database")
        with psycopg2.connect(database_dsn(settings.DATABASES_DATA["my_database"])) as conn:
            conn.cursor().execute(
                """
                CREATE TABLE IF NOT EXISTS test_table AS (
                    SELECT 1 as a, 2 as b
                );
            """
            )
            conn.commit()
            yield database
            conn.cursor().execute("DROP TABLE test_table")

    def test_unauthorised_link(self, client):
        link = factories.SourceLinkFactory()
        response = client.get(
            reverse("datasets:data_cut_source_link_preview", args=(link.dataset.id, link.id))
        )
        assert response.status_code == 403

    @override_flag(settings.DATA_CUT_ENHANCED_PREVIEW_FLAG, active=True)
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_authorised_link(self, access_type, client, mocker):
        dataset = factories.DataSetFactory(user_access_type=access_type)
        link = factories.SourceLinkFactory(
            id="158776ec-5c40-4c58-ba7c-a3425905ec45",
            dataset=dataset,
            url="s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.csv",
        )
        mock_client = mocker.patch("dataworkspace.apps.core.boto3_client.boto3.client")
        mock_client().head_object.return_value = {"ContentType": "text/csv"}
        csv_content = b"header1,header2\nrow1 col1, row1 col2\nrow2 col1, row2 col2\n"
        mock_client().get_object.return_value = {
            "ContentType": "text/plain",
            "ContentLength": len(csv_content),
            "Body": StreamingBody(io.BytesIO(csv_content), len(csv_content)),
        }
        response = client.get(
            reverse("datasets:data_cut_source_link_preview", args=(dataset.id, link.id))
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert (
            "<thead>"
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header">header1</th>'
            '<th class="govuk-table__header">header2</th>'
            "</tr>"
            "</thead><tbody>"
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">row1 col1</td>'
            '<td class="govuk-table__cell">row1 col2</td>'
            "</tr>"
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">row2 col1</td>'
            '<td class="govuk-table__cell">row2 col2</td>'
            "</tr></tbody>"
        ) in "".join([s.strip() for s in content.splitlines() if s.strip()])
        assert "Showing <strong>2</strong> records." in content
        assert "Download as CSV" in content

    @override_flag(settings.DATA_CUT_ENHANCED_PREVIEW_FLAG, active=True)
    def test_unauthorised_query(self, client, test_db):
        dataset = factories.DataSetFactory(
            type=DataSetType.MASTER,
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
        )

        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query="SELECT 1 as a, 2 as b",
            reviewed=False,
        )
        response = client.get(
            reverse("datasets:data_cut_query_preview", args=(dataset.id, query.id))
        )
        assert response.status_code == 403

    @override_flag(settings.DATA_CUT_ENHANCED_PREVIEW_FLAG, active=True)
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_authorised_query(self, access_type, client, test_db):
        dataset = factories.DataSetFactory(type=DataSetType.MASTER, user_access_type=access_type)

        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=test_db,
            query="SELECT 1 as a, 2 as b",
            reviewed=True,
        )
        response = client.get(
            reverse("datasets:data_cut_query_preview", args=(dataset.id, query.id))
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert (
            "<thead>"
            '<tr class="govuk-table__row">'
            '<th class="govuk-table__header">a</th>'
            '<th class="govuk-table__header">b</th>'
            "</tr>"
            "</thead><tbody>"
            '<tr class="govuk-table__row">'
            '<td class="govuk-table__cell">1</td>'
            '<td class="govuk-table__cell">2</td>'
            "</tr></tbody>"
        ) in "".join([s.strip() for s in content.splitlines() if s.strip()])
        assert "Showing <strong>1</strong> record." in content
        assert "Download as CSV" in content
