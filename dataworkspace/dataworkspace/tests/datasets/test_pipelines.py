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
def test_edit_pipeline(mock_sync, staff_client):
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


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.run_pipeline")
def test_run_pipeline(mock_run, staff_client):
    pipeline = factories.PipelineFactory.create()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:run", args=(pipeline.id,)),
        follow=True,
    )
    assert "Pipeline triggered successfully" in resp.content.decode(resp.charset)


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.stop_pipeline")
def test_stop_pipeline(mock_stop, staff_client):
    pipeline = factories.PipelineFactory.create()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:stop", args=(pipeline.id,)),
        follow=True,
    )
    assert "Pipeline stopped successfully" in resp.content.decode(resp.charset)



@pytest.mark.django_db
def test_pipeline_log_no_log(staff_client, requests_mock):
    pipeline = factories.PipelineFactory.create()

    requests_mock.get(f"https://google.com/{pipeline.pk}", status_code=400)
    resp = staff_client.post(
        reverse("pipelines:logs", args=(pipeline.id,)),
        follow=True,
    )
    assert "error" in resp.content.decode(resp.charset)


@pytest.mark.django_db
def test_pipeline_log_success(staff_client, requests_mock):
    pipeline = factories.PipelineFactory.create()

    requests_mock.get(f"https://google.com/{pipeline.pk}", json={"success": "OK"}, status_code=200)
    resp = staff_client.post(
        reverse("pipelines:logs", args=(pipeline.id,)),
        follow=True,
    )
    assert "success" in resp.content.decode(resp.charset)


@pytest.mark.django_db
def test_pipeline_log_decode_error(staff_client, requests_mock):
    pipeline = factories.PipelineFactory.create()

    requests_mock.get(f"https://google.com/{pipeline.pk}", text="response text", status_code=200)
    resp = staff_client.post(
        reverse("pipelines:logs", args=(pipeline.id,)),
        follow=True,
    )
    assert "response text" in resp.content.decode(resp.charset)
