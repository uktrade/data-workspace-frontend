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
