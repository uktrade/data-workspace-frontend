import pytest

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    get_code_snippets,
)
from dataworkspace.tests.factories import DataSetFactory, SourceTableFactory


def test_dataset_type_to_manage_unpublished_permission_codename():
    assert (
        dataset_type_to_manage_unpublished_permission_codename(0)
        == 'datasets.manage_unpublished_reference_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(DataSet.TYPE_DATA_CUT)
        == 'datasets.manage_unpublished_datacut_datasets'
    )
    assert (
        dataset_type_to_manage_unpublished_permission_codename(
            DataSet.TYPE_MASTER_DATASET
        )
        == 'datasets.manage_unpublished_master_datasets'
    )


@pytest.mark.django_db
def test_get_code_snippets(metadata_db):
    ds = DataSetFactory.create(type=DataSetType.MASTER.value)
    sourcetable = SourceTableFactory.create(
        dataset=ds, schema="public", table="MY_LOVELY_TABLE"
    )

    snippets = get_code_snippets(sourcetable)
    assert """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50""" in snippets['python']
    assert """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50""" in snippets['r']
    assert snippets['sql'] == """SELECT * FROM "public"."MY_LOVELY_TABLE" LIMIT 50"""
