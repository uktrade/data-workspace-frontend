import io
import uuid
from unittest import mock

import psycopg2
import pytest
from botocore.response import StreamingBody
from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import SourceLink, DataSet
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories


@pytest.mark.parametrize(
    "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
)
def test_link_data_cut_doesnt_have_preview(access_type, client):
    data_cut = factories.DataSetFactory(user_access_type=access_type, published=True)
    factories.SourceLinkFactory(dataset=data_cut)

    response = client.get(data_cut.get_absolute_url())

    assert response.status_code == 200
    # assert 'No preview available' in response.rendered_content


@pytest.mark.django_db
class TestDatasetViews:
    def test_homepage_unauth(self, unauthenticated_client):
        response = unauthenticated_client.get(reverse("root"))
        assert response.status_code == 403

    def test_homepage(self, client):
        response = client.get(reverse("root"))
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "request_client,factory,published,status",
        [
            ("client", factories.DataSetFactory, True, 200),
            ("client", factories.ReferenceDatasetFactory, True, 200),
            ("client", factories.DataSetFactory, False, 403),
            ("client", factories.ReferenceDatasetFactory, False, 403),
            ("staff_client", factories.DataSetFactory, True, 200),
            ("staff_client", factories.ReferenceDatasetFactory, True, 200),
            ("staff_client", factories.DataSetFactory, False, 200),
            ("staff_client", factories.ReferenceDatasetFactory, False, 200),
        ],
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_dataset_detail_view(self, request_client, factory, published, status):
        ds = factory.create(published=published)
        response = request_client.get(ds.get_absolute_url())
        assert response.status_code == status

    def test_deleted_dataset_detail_view(self, client):
        ds = factories.DataSetFactory.create(published=True, deleted=True)
        response = client.get(ds.get_absolute_url())
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_dataset_detail_view_invalid_uuid(self, client):
        response = client.get("/datasets/0c2825e1")
        assert response.status_code == 404

    @override_settings(DEBUG=False, GTM_CONTAINER_ID="test")
    @pytest.mark.parametrize(
        "factory",
        [
            factories.MasterDataSetFactory,
            factories.DatacutDataSetFactory,
            factories.ReferenceDatasetFactory,
        ],
    )
    def test_renders_gtm_push(self, client, factory):
        ds = factory.create(published=True, deleted=False)
        sso_id = uuid.uuid4()
        headers = {
            "HTTP_SSO_PROFILE_USER_ID": sso_id,
        }
        response = client.get(ds.get_absolute_url(), **headers)
        assert "dataLayer.push({" in response.content.decode(response.charset)

    @override_settings(REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS=1)
    @pytest.mark.django_db
    def test_reference_dataset_detail_view(self, client):
        factories.DataSetFactory.create()
        rds = factories.ReferenceDatasetFactory.create(table_name="test_detail_view")
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="id", data_type=2, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="name", data_type=1
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=rds, name="desc", data_type=1
        )
        rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 1,
                field2.column_name: "Test record",
                field3.column_name: "Test Desc 1",
            },
        )
        rds.save_record(
            None,
            {
                "reference_dataset": rds,
                field1.column_name: 2,
                field2.column_name: "Ánd again",
                field3.column_name: None,
            },
        )

        response = client.get(rds.get_absolute_url())
        assert response.status_code == 200
        assert rds.name.encode("utf-8") in response.content
        assert response.context["record_count"] == 2
        assert response.context["preview_limit"] == 1
        assert response.context["records"].count() == 1
        actual_record = response.context["records"].first()
        assert getattr(actual_record, field1.column_name) == 1
        assert getattr(actual_record, field2.column_name) == "Test record"
        assert getattr(actual_record, field3.column_name) == "Test Desc 1"


class TestSourceLinkDownloadView:
    def test_forbidden_dataset(self, client):
        dataset = factories.DataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        link = factories.SourceLinkFactory(
            id="158776ec-5c40-4c58-ba7c-a3425905ec45",
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url="http://example.com",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = client.get(
            reverse(
                "datasets:dataset_source_link_download",
                kwargs={"dataset_uuid": dataset.id, "source_link_id": link.id},
            )
        )
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_download_external_file(self, access_type, request_client, published):
        dataset = factories.DataSetFactory.create(
            published=published, user_access_type=access_type
        )
        link = factories.SourceLinkFactory(
            dataset=dataset,
            link_type=SourceLink.TYPE_EXTERNAL,
            url="http://example.com",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(
            reverse(
                "datasets:dataset_source_link_download",
                kwargs={"dataset_uuid": dataset.id, "source_link_id": link.id},
            ),
            follow=False,
        )
        assert response.status_code == 302
        assert EventLog.objects.count() == log_count + 1
        assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    @mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
    def test_download_local_file(self, mock_client, request_client, published, access_type):
        dataset = factories.DataSetFactory.create(
            published=published, user_access_type=access_type
        )
        link = factories.SourceLinkFactory(
            id="158776ec-5c40-4c58-ba7c-a3425905ec45",
            dataset=dataset,
            link_type=SourceLink.TYPE_LOCAL,
            url="s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.txt",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        mock_client().get_object.return_value = {
            "ContentType": "text/plain",
            "ContentLength": len(b"This is a test file"),
            "Body": StreamingBody(io.BytesIO(b"This is a test file"), len(b"This is a test file")),
        }
        response = request_client.get(
            reverse(
                "datasets:dataset_source_link_download",
                kwargs={"dataset_uuid": dataset.id, "source_link_id": link.id},
            )
        )
        assert response.status_code == 200
        assert list(response.streaming_content)[0] == b"This is a test file"
        assert response["content-length"] == str(len(b"This is a test file"))
        mock_client().get_object.assert_called_with(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key=link.url
        )
        assert EventLog.objects.count() == log_count + 1
        assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1


class TestSourceViewDownloadView:
    def test_forbidden_dataset(self, client):
        dataset = factories.DataSetFactory(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        source_view = factories.SourceViewFactory(dataset=dataset)
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = client.get(source_view.get_absolute_url())
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    def test_missing_view(self, access_type, client):
        dataset = factories.DataSetFactory(user_access_type=access_type)
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name="my_database"),
        )
        download_count = dataset.number_of_downloads
        response = client.get(source_view.get_absolute_url())
        assert response.status_code == 404
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_view_download(self, access_type, request_client, published):
        dsn = database_dsn(settings.DATABASES_DATA["my_database"])
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE if not exists download_test_table (field2 int,field1 varchar(255));
                TRUNCATE TABLE download_test_table;
                INSERT INTO download_test_table VALUES(1, 'record1');
                INSERT INTO download_test_table VALUES(2, 'record2');
                CREATE OR REPLACE VIEW download_test_view AS SELECT * FROM download_test_table;
                """
            )

        dataset = factories.DataSetFactory(user_access_type=access_type, published=published)
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name="my_database"),
            schema="public",
            view="download_test_view",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(source_view.get_absolute_url())
        assert response.status_code == 200
        assert (
            b"".join(response.streaming_content)
            == b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.parametrize(
        "access_type", (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
    )
    @pytest.mark.django_db
    def test_materialized_view_download(self, access_type, request_client, published):
        dsn = database_dsn(settings.DATABASES_DATA["my_database"])
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE if not exists materialized_test_table (field2 int,field1 varchar(255));
                TRUNCATE TABLE materialized_test_table;
                INSERT INTO materialized_test_table VALUES(1, 'record1');
                INSERT INTO materialized_test_table VALUES(2, 'record2');
                DROP MATERIALIZED VIEW IF EXISTS materialized_test_view;
                CREATE MATERIALIZED VIEW materialized_test_view AS
                SELECT * FROM materialized_test_table;
                """
            )
        dataset = factories.DataSetFactory(user_access_type=access_type, published=published)
        source_view = factories.SourceViewFactory(
            dataset=dataset,
            database=factories.DatabaseFactory(memorable_name="my_database"),
            schema="public",
            view="materialized_test_view",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = request_client.get(source_view.get_absolute_url())
        assert response.status_code == 200
        assert (
            b"".join(response.streaming_content)
            == b'"field2","field1"\r\n1,"record1"\r\n2,"record2"\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count + 1


class TestCustomQueryDownloadView:
    def _get_dsn(self):
        return database_dsn(settings.DATABASES_DATA["my_database"])

    def _get_database(self):
        return factories.DatabaseFactory(memorable_name="my_database")

    def _create_query(self, sql, reviewed=True, published=True, data_grid_enabled=False):
        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS custom_query_test (
                    id INT,
                    name VARCHAR(255),
                    date DATE
                );
                TRUNCATE TABLE custom_query_test;
                INSERT INTO custom_query_test VALUES(1, 'the first record', NULL);
                INSERT INTO custom_query_test VALUES(2, 'the second record', '2019-01-01');
                INSERT INTO custom_query_test VALUES(3, 'the last record', NULL);
                """
            )
        dataset = factories.DataSetFactory(
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION, published=published
        )
        return factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=self._get_database(),
            query=sql,
            reviewed=reviewed,
            data_grid_enabled=data_grid_enabled,
        )

    def test_forbidden_dataset(self, client):
        dataset = factories.DataSetFactory(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        query = factories.CustomDatasetQueryFactory(
            dataset=dataset,
            database=self._get_database(),
            query="SELECT * FROM a_table",
        )
        log_count = EventLog.objects.count()
        download_count = dataset.number_of_downloads
        response = client.get(query.get_absolute_url())
        assert response.status_code == 403
        assert EventLog.objects.count() == log_count
        assert DataSet.objects.get(pk=dataset.id).number_of_downloads == download_count

    def test_invalid_sql(self, client):
        query = self._create_query("SELECT * FROM table_that_does_not_exist;")
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

    def test_dangerous_sql(self, client):
        # Test drop table
        query = self._create_query("DROP TABLE custom_query_test;")
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('custom_query_test')")
            assert cursor.fetchone()[0] == "custom_query_test"

        # Test delete records
        query = self._create_query("DELETE FROM custom_query_test;")
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM custom_query_test")
            assert cursor.fetchone()[0] == 3

        # Test update records
        query = self._create_query("UPDATE custom_query_test SET name='updated';")
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM custom_query_test WHERE name='updated'")
            assert cursor.fetchone()[0] == 0

        # Test insert record
        query = self._create_query("INSERT INTO custom_query_test (id, name) VALUES(4, 'added')")
        with pytest.raises(Exception):
            list(client.get(query.get_absolute_url()).streaming_content)

        with psycopg2.connect(self._get_dsn()) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM custom_query_test")
            assert cursor.fetchone()[0] == 3

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_valid_sql(self, request_client, published):
        query = self._create_query(
            "SELECT * FROM custom_query_test WHERE id IN (1, 3)", published=published
        )
        log_count = EventLog.objects.count()
        download_count = query.dataset.number_of_downloads
        response = request_client.get(query.get_absolute_url())
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == (
            b'"id","name","date"\r\n1,"the first record",""\r\n'
            b'3,"the last record",""\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 1
        assert EventLog.objects.latest().event_type == EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD
        assert DataSet.objects.get(pk=query.dataset.id).number_of_downloads == download_count + 1

    @pytest.mark.parametrize(
        "request_client,published",
        [("client", True), ("staff_client", True), ("staff_client", False)],
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_valid_sql_data_grid_preview(self, request_client, published):
        query = self._create_query(
            "SELECT * FROM custom_query_test WHERE id IN (1, 3)",
            published=published,
            data_grid_enabled=True,
        )
        log_count = EventLog.objects.count()

        url = f"{query.get_grid_data_url()}?download=1"

        response = request_client.post(
            url,
            data={
                "export_file_name": "filename.csv",
                "columns": ["id", "name"],
                "filters": "{}",
            },
        )

        assert response.status_code == 200
        assert b"".join(response.streaming_content) == (
            b'"id","name"\r\n1,"the first record"\r\n'
            b'3,"the last record"\r\n"Number of rows: 2"\r\n'
        )
        assert EventLog.objects.count() == log_count + 2

        latest_events = EventLog.objects.all().order_by("-id")[:2]

        assert latest_events[0].event_type == EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE

        assert latest_events[1].event_type == EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD

    @pytest.mark.parametrize(
        "request_client, reviewed, status",
        (
            ("sme_client", False, 403),
            ("sme_client", True, 200),
            ("staff_client", False, 200),
            ("staff_client", True, 200),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_only_superuser_can_download_unreviewed_query(self, request_client, reviewed, status):
        query = self._create_query(
            "SELECT * FROM custom_query_test", published=False, reviewed=reviewed
        )

        response = request_client.get(query.get_absolute_url())
        assert response.status_code == status
