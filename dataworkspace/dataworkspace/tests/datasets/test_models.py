import io
from collections import OrderedDict
from datetime import datetime

import botocore
import mock
import pytest
from botocore.response import StreamingBody
from pytz import UTC

from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import SourceLink
from dataworkspace.tests import factories


def test_clone_dataset(db):
    ds = factories.DataSetFactory.create(published=True)
    clone = ds.clone()

    assert clone.id
    assert clone.id != ds.id
    assert clone.slug == ""
    assert clone.number_of_downloads == 0
    assert clone.name == f"Copy of {ds.name}"
    assert clone.published_at is None
    assert not clone.published


def test_clone_dataset_copies_related_objects(db):
    ds = factories.DataSetFactory.create(published=True)

    factories.DataSetUserPermissionFactory(dataset=ds)
    factories.SourceLinkFactory(dataset=ds)
    factories.SourceViewFactory(dataset=ds)
    factories.SourceTableFactory(dataset=ds)
    factories.CustomDatasetQueryFactory(dataset=ds)

    clone = ds.clone()

    assert not clone.datasetuserpermission_set.all()
    assert [obj.dataset for obj in clone.sourcelink_set.all()] == [clone]
    assert [obj.dataset for obj in clone.sourceview_set.all()] == [clone]
    assert [obj.dataset for obj in clone.sourcetable_set.all()] == [clone]
    assert [obj.dataset for obj in clone.customdatasetquery_set.all()] == [clone]

    assert ds.datasetuserpermission_set.all()
    assert [obj.dataset for obj in ds.sourcelink_set.all()] == [ds]
    assert [obj.dataset for obj in ds.sourceview_set.all()] == [ds]
    assert [obj.dataset for obj in ds.sourcetable_set.all()] == [ds]
    assert [obj.dataset for obj in ds.customdatasetquery_set.all()] == [ds]


@pytest.mark.parametrize(
    "factory",
    (
        factories.SourceTableFactory,
        factories.SourceViewFactory,
        factories.SourceLinkFactory,
        factories.CustomDatasetQueryFactory,
    ),
)
def test_dataset_source_reference_code(db, factory):
    ref_code1 = factories.DatasetReferenceCodeFactory(code="Abc")
    ref_code2 = factories.DatasetReferenceCodeFactory(code="Def")
    ds = factories.DataSetFactory(reference_code=ref_code1, user_access_type=UserAccessType.OPEN)
    source = factory(dataset=ds)
    assert source.source_reference == "ABC00001"

    # Change to a new reference code
    ds.reference_code = ref_code2
    ds.save()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference == "DEF00001"

    # Unset the reference code
    ds.reference_code = None
    ds.save()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference is None

    # Ensure numbers are incremented
    ds.reference_code = ref_code1
    ds.save()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference == "ABC00002"

    # Delete the reference code
    ref_code1.delete()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference is None


@pytest.mark.parametrize(
    "factory",
    (
        factories.SourceTableFactory,
        factories.SourceViewFactory,
        factories.CustomDatasetQueryFactory,
    ),
)
def test_dataset_source_filename(db, factory):
    ds1 = factories.DataSetFactory(reference_code=factories.DatasetReferenceCodeFactory(code="DW"))
    source1 = factory(dataset=ds1, name="A test source")
    assert source1.get_filename() == "DW00001-a-test-source.csv"

    ds2 = factories.DataSetFactory()
    source2 = factory(dataset=ds2, name="A test source")
    assert source2.get_filename() == "a-test-source.csv"


def test_source_link_filename(db):
    ds1 = factories.DataSetFactory(reference_code=factories.DatasetReferenceCodeFactory(code="DW"))
    source1 = factories.SourceLinkFactory(
        dataset=ds1,
        name="A test source",
        url="s3://csv-pipelines/my-data.csv.zip",
        link_type=SourceLink.TYPE_LOCAL,
    )
    assert source1.get_filename() == "DW00001-a-test-source.zip"

    ds2 = factories.DataSetFactory()
    source2 = factories.SourceLinkFactory(
        dataset=ds2,
        name="A test source",
        url="s3://csv-pipelines/my-data.csv",
        link_type=SourceLink.TYPE_LOCAL,
    )
    assert source2.get_filename() == "a-test-source.csv"

    ds3 = factories.DataSetFactory()
    source3 = factories.SourceLinkFactory(
        dataset=ds3,
        name="A test source",
        url="http://www.google.com/index.html",
        link_type=SourceLink.TYPE_EXTERNAL,
    )
    assert source3.get_filename() == "a-test-source.csv"


@pytest.mark.django_db
def test_source_table_data_last_updated(metadata_db):
    dataset = factories.DataSetFactory()
    table = factories.SourceTableFactory(
        dataset=dataset, database=metadata_db, schema="public", table="table1"
    )
    assert table.get_data_last_updated_date() == datetime(2020, 9, 2, 0, 1, 0, tzinfo=UTC)

    table = factories.SourceTableFactory(
        dataset=dataset, database=metadata_db, schema="public", table="doesntexist"
    )
    assert table.get_data_last_updated_date() is None


@pytest.mark.django_db
def test_custom_query_data_last_updated(metadata_db):
    dataset = factories.DataSetFactory()

    # Ensure the earliest "last updated" date is returned when
    # there are multiple tables in the query
    query = factories.CustomDatasetQueryFactory(
        dataset=dataset,
        database=metadata_db,
        query="select * from table1 join table2 on 1=1",
    )
    factories.CustomDatasetQueryTableFactory(query=query, schema="public", table="table1")
    factories.CustomDatasetQueryTableFactory(query=query, schema="public", table="table2")
    assert query.get_data_last_updated_date() == datetime(2020, 9, 1, 0, 1, 0, tzinfo=UTC)

    # Ensure a single table returns the last update date
    query = factories.CustomDatasetQueryFactory(
        dataset=dataset,
        database=metadata_db,
        query="select * from table1",
    )
    factories.CustomDatasetQueryTableFactory(query=query, schema="public", table="table1")
    assert query.get_data_last_updated_date() == datetime(2020, 9, 2, 0, 1, 0, tzinfo=UTC)

    # Ensure None is returned if we don't have any metadata for the tables
    query = factories.CustomDatasetQueryFactory(
        dataset=dataset,
        database=metadata_db,
        query="select * from table3",
    )
    assert query.get_data_last_updated_date() is None

    # Ensure None is returned if the last updated date is null
    query = factories.CustomDatasetQueryFactory(
        dataset=dataset,
        database=metadata_db,
        query="select * from table4",
    )
    assert query.get_data_last_updated_date() is None


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.views.boto3.client")
def test_source_link_data_last_updated(mock_client):
    dataset = factories.DataSetFactory.create()
    local_link = factories.SourceLinkFactory(
        dataset=dataset,
        link_type=SourceLink.TYPE_LOCAL,
        url="s3://sourcelink/158776ec-5c40-4c58-ba7c-a3425905ec45/test.txt",
    )

    # Returns last modified date if the file exists
    mock_client().head_object.return_value = {
        "ContentType": "text/plain",
        "LastModified": datetime(2020, 9, 2, 0, 1, 0),
    }
    assert local_link.get_data_last_updated_date() == datetime(2020, 9, 2, 0, 1, 0)

    # Returns None if file does not exist on s3
    mock_client().head_object.side_effect = [
        botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="head_object",
        )
    ]
    assert local_link.get_data_last_updated_date() is None

    # External links never have a last updated date
    external_link = factories.SourceLinkFactory(
        dataset=dataset,
        link_type=SourceLink.TYPE_EXTERNAL,
        url="http://www.example.com",
    )
    assert external_link.get_data_last_updated_date() is None


@pytest.mark.django_db
class TestSourceLinkPreview:
    @pytest.fixture
    def mock_client(self, mocker):
        return mocker.patch("dataworkspace.apps.datasets.models.boto3.client")

    def test_not_s3_link(self):
        link = factories.SourceLinkFactory(url="http://example.com/a-file.csv")
        assert link.get_preview_data() == (None, [])

    def test_failed_reading_from_s3(self, mock_client):
        link = factories.SourceLinkFactory(url="s3://a/path/to/a/file.csv")
        mock_client().head_object.side_effect = [
            botocore.exceptions.ClientError(
                error_response={"Error": {"Message": "it failed"}},
                operation_name="head_object",
            )
        ]
        assert link.get_preview_data() == (None, [])

    def test_file_not_csv(self, mock_client):
        link = factories.SourceLinkFactory(url="s3://a/path/to/a/file.txt")
        mock_client().head_object.return_value = {"ContentType": "text/csv"}
        assert link.get_preview_data() == (None, [])

    def test_preview_csv(self, mock_client):
        link = factories.SourceLinkFactory(url="s3://a/path/to/a/file.csv")
        mock_client().head_object.return_value = {"ContentType": "text/csv"}
        csv_content = b"col1,col2\nrow1-col1, row1-col2\nrow2-col1, row2-col2\ntrailing"
        mock_client().get_object.return_value = {
            "ContentType": "text/plain",
            "ContentLength": len(csv_content),
            "Body": StreamingBody(io.BytesIO(csv_content), len(csv_content)),
        }
        assert link.get_preview_data() == (
            ["col1", "col2"],
            [
                OrderedDict([("col1", "row1-col1"), ("col2", " row1-col2")]),
                OrderedDict([("col1", "row2-col1"), ("col2", " row2-col2")]),
            ],
        )
