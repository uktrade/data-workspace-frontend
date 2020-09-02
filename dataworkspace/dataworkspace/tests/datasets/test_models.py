import psqlparse
import pytest

from dataworkspace.apps.datasets.models import SourceLink
from dataworkspace.tests import factories


def test_clone_dataset(db):
    ds = factories.DataSetFactory.create(published=True)
    clone = ds.clone()

    assert clone.id
    assert clone.id != ds.id
    assert clone.slug == ''
    assert clone.number_of_downloads == 0
    assert clone.name == f'Copy of {ds.name}'
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
    'factory',
    (
        factories.SourceTableFactory,
        factories.SourceViewFactory,
        factories.SourceLinkFactory,
        factories.CustomDatasetQueryFactory,
    ),
)
def test_dataset_source_reference_code(db, factory):
    ref_code1 = factories.DatasetReferenceCodeFactory(code='Abc')
    ref_code2 = factories.DatasetReferenceCodeFactory(code='Def')
    ds = factories.DataSetFactory(reference_code=ref_code1)
    source = factory(dataset=ds)
    assert source.source_reference == 'ABC00001'

    # Change to a new reference code
    ds.reference_code = ref_code2
    ds.save()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference == 'DEF00001'

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
    assert source.source_reference == 'ABC00002'

    # Delete the reference code
    ref_code1.delete()
    ds.refresh_from_db()

    source.refresh_from_db()
    assert source.source_reference is None


@pytest.mark.parametrize(
    'factory',
    (
        factories.SourceTableFactory,
        factories.SourceViewFactory,
        factories.CustomDatasetQueryFactory,
    ),
)
def test_dataset_source_filename(db, factory):
    ds1 = factories.DataSetFactory(
        reference_code=factories.DatasetReferenceCodeFactory(code='DW')
    )
    source1 = factory(dataset=ds1, name='A test source')
    assert source1.get_filename() == 'DW00001-a-test-source.csv'

    ds2 = factories.DataSetFactory()
    source2 = factory(dataset=ds2, name='A test source')
    assert source2.get_filename() == 'a-test-source.csv'


def test_source_link_filename(db):
    ds1 = factories.DataSetFactory(
        reference_code=factories.DatasetReferenceCodeFactory(code='DW')
    )
    source1 = factories.SourceLinkFactory(
        dataset=ds1,
        name='A test source',
        url="s3://csv-pipelines/my-data.csv.zip",
        link_type=SourceLink.TYPE_LOCAL,
    )
    assert source1.get_filename() == 'DW00001-a-test-source.zip'

    ds2 = factories.DataSetFactory()
    source2 = factories.SourceLinkFactory(
        dataset=ds2,
        name='A test source',
        url="s3://csv-pipelines/my-data.csv",
        link_type=SourceLink.TYPE_LOCAL,
    )
    assert source2.get_filename() == 'a-test-source.csv'

    ds3 = factories.DataSetFactory()
    source3 = factories.SourceLinkFactory(
        dataset=ds3,
        name='A test source',
        url="http://www.google.com/index.html",
        link_type=SourceLink.TYPE_EXTERNAL,
    )
    assert source3.get_filename() == 'a-test-source.csv'


def test_dataset_parsed_query_tables(db):
    ds = factories.DataSetFactory.create(published=True)

    blank_query = factories.CustomDatasetQueryFactory(dataset=ds)
    assert not blank_query.parsed_query_tables

    standard_query = factories.CustomDatasetQueryFactory(
        dataset=ds, query='select * from foo'
    )
    assert standard_query.parsed_query_tables == ['foo']

    join_query = factories.CustomDatasetQueryFactory(
        dataset=ds, query='select * from foo join bar on foo.id = bar.id'
    )
    assert sorted(join_query.parsed_query_tables) == ['bar', 'foo']

    with_query = factories.CustomDatasetQueryFactory(
        dataset=ds, query='with test as (select * from foo) select * from test'
    )
    assert sorted(with_query.parsed_query_tables) == ['foo', 'test']

    bad_query = factories.CustomDatasetQueryFactory(dataset=ds, query='select * from')
    with pytest.raises(psqlparse.exceptions.PSqlParseError):
        bad_query.parsed_query_tables  # pylint: disable=pointless-statement
