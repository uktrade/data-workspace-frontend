import pytest
from django.urls import reverse
from mock import mock

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.tests import factories


@pytest.mark.django_db
@pytest.mark.parametrize(
    "table_name,expected_output,added_pipelines",
    (
        ("no_dot", "Table name must be in the format &lt;schema&gt;.&lt;table name&gt;", 0),
        (
            ("a" * 65) + ".table_name",
            "Schema name must be less than 63 characters",
            0,
        ),
        (
            "schema_name." + ("a" * 45),
            "Table name must be less than 42 characters",
            0,
        ),
        (
            "a_schema.a_table",
            "Pipeline created successfully",
            1,
        ),
    ),
)
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline(mock_sync, table_name, expected_output, added_pipelines, staff_client):
    pipeline_count = Pipeline.objects.count()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create"),
        data={"table_name": table_name, "sql_query": "SELECT 1"},
        follow=True,
    )
    assert expected_output in resp.content.decode(resp.charset)
    assert pipeline_count + added_pipelines == Pipeline.objects.count()


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_edit_pipeline(mock_delete, staff_client):
    pipeline = factories.PipelineFactory.create()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:edit", args=(pipeline.id,)),
        data={"table_name": pipeline.table_name, "sql_query": "SELECT 2"},
        follow=True,
    )
    assert "Pipeline updated successfully" in resp.content.decode(resp.charset)
    pipeline.refresh_from_db()
    assert pipeline.sql_query == "SELECT 2"


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.delete_pipeline_from_dataflow")
def test_delete_pipeline(mock_delete, staff_client):
    pipeline = factories.PipelineFactory.create()
    pipeline_count = Pipeline.objects.count()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:delete", args=(pipeline.id,)),
        follow=True,
    )
    assert "Pipeline deleted successfully" in resp.content.decode(resp.charset)
    assert pipeline_count - 1 == Pipeline.objects.count()
