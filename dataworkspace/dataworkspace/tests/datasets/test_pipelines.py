import pytest
from django.urls import reverse
from mock import mock

from requests import RequestException

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.tests import factories


@pytest.mark.django_db
@pytest.mark.parametrize(
    "table_name,expected_output,added_pipelines",
    (
        (
            "no_dot",
            "Table name must be in the format schema.table or &quot;schema&quot;.&quot;table&quot;",
            0,
        ),
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
def test_create_sql_pipeline(
    mock_sync, table_name, expected_output, added_pipelines, staff_client
):
    pipeline_count = Pipeline.objects.count()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": table_name, "sql": "SELECT 1"},
        follow=True,
    )
    assert expected_output in resp.content.decode(resp.charset)
    assert pipeline_count + added_pipelines == Pipeline.objects.count()


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_sharepoint_pipeline(mock_sync, staff_client):
    pipeline_count = Pipeline.objects.count()
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sharepoint"),
        data={
            "type": "sharepoint",
            "table_name": "test.sharepoint1",
            "site_name": "A Site",
            "list_name": "A List",
        },
        follow=True,
    )
    assert "Pipeline created successfully" in resp.content.decode(resp.charset)
    assert pipeline_count + 1 == Pipeline.objects.count()


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_valid_sql(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": "test", "sql": "SELECT bar as 1;"},
        follow=True,
    )
    assert b"syntax error" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_single_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": "test", "sql": "SELECT 1; SELECT 2;"},
        follow=True,
    )
    assert b"Enter a single statement" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_drop_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": "test", "sql": "DROP TABLE foo;"},
        follow=True,
    )
    assert b"Only SELECT statements are supported" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_create_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": "test", "sql": "CREATE TABLE foo (f1 int);"},
        follow=True,
    )
    assert b"Only SELECT statements are supported" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_duplicate_column_names(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"type": "sql", "table_name": "test", "sql": "SELECT 1 AS foo, 2 AS foo;"},
        follow=True,
    )
    assert b"Duplicate column names found" in resp.content


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_edit_sql_pipeline(mock_sync, staff_client):
    pipeline = factories.PipelineFactory.create(config={"sql": "SELECT 1"})
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:edit-sql", args=(pipeline.id,)),
        data={"type": "sql", "table_name": pipeline.table_name, "sql": "SELECT 2"},
        follow=True,
    )
    assert "Pipeline updated successfully" in resp.content.decode(resp.charset)
    pipeline.refresh_from_db()
    assert pipeline.config["sql"] == "SELECT 2"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "intial_notes,edited_notes",
    (
        (
            "sql pipeline notes",
            "edited sql pipeline notes",
        ),
        (
            "",
            "edited sql pipeline notes",
        ),
        (
            "sql pipeline notes",
            "",
        ),
    ),
)
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_edit_sql_pipeline_with_notes(
    mock_sync,
    staff_client,
    intial_notes,
    edited_notes,
):
    pipeline = factories.PipelineFactory.create(config={"sql": "SELECT 1"}, notes=intial_notes)
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:edit-sql", args=(pipeline.id,)),
        data={
            "type": "sql",
            "table_name": pipeline.table_name,
            "sql": "SELECT 2",
            "notes": edited_notes,
        },
        follow=True,
    )
    assert "Pipeline updated successfully" in resp.content.decode(resp.charset)
    pipeline.refresh_from_db()
    assert pipeline.config["sql"] == "SELECT 2"
    assert pipeline.notes == edited_notes


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_edit_sharepoint_pipeline(mock_sync, staff_client):
    pipeline = factories.PipelineFactory.create(
        type="sharepoint", config={"site_name": "site1", "list_name": "list1"}
    )
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:edit-sharepoint", args=(pipeline.id,)),
        data={
            "type": "sql",
            "table_name": pipeline.table_name,
            "site_name": "site2",
            "list_name": "list2",
        },
        follow=True,
    )
    assert "Pipeline updated successfully" in resp.content.decode(resp.charset)
    pipeline.refresh_from_db()
    assert pipeline.config == {"site_name": "site2", "list_name": "list2"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "intial_notes,edited_notes",
    (
        (
            "sharepoint pipeline notes",
            "edited sharepoint pipeline notes",
        ),
        (
            "",
            "edited sharepoint pipeline notes",
        ),
        (
            "sharepoint pipeline notes",
            "",
        ),
    ),
)
@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_edit_sharepoint_pipeline_with_notes(mock_sync, staff_client, intial_notes, edited_notes):
    pipeline = factories.PipelineFactory.create(
        type="sharepoint",
        config={"site_name": "site1", "list_name": "list1", "notes": intial_notes},
    )
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:edit-sharepoint", args=(pipeline.id,)),
        data={
            "type": "sql",
            "table_name": pipeline.table_name,
            "site_name": "site2",
            "list_name": "list2",
            "notes": edited_notes,
        },
        follow=True,
    )
    assert "Pipeline updated successfully" in resp.content.decode(resp.charset)
    pipeline.refresh_from_db()
    assert pipeline.config == {"site_name": "site2", "list_name": "list2"}
    assert pipeline.notes == edited_notes


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
    pipeline = factories.PipelineFactory.create(type="sql")
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:run", args=(pipeline.id,)),
        follow=True,
    )
    assert "Pipeline triggered successfully" in resp.content.decode(resp.charset)


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.datasets.pipelines.views.stop_pipeline")
def test_stop_pipeline(mock_stop, staff_client):
    pipeline = factories.PipelineFactory.create(type="sharepoint")
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:stop", args=(pipeline.id,)),
        follow=True,
    )
    assert "Pipeline stopped successfully" in resp.content.decode(resp.charset)


@pytest.mark.django_db
def test_pipeline_log_success(staff_client, mocker):
    pipeline = factories.PipelineFactory.create(type="sharepoint")
    _return_value = [
        {
            "task_1": "...",
        }
    ]
    mocker.patch(
        "dataworkspace.apps.datasets.pipelines.views.get_pipeline_logs",
        return_value=_return_value,
    )
    resp = staff_client.get(
        reverse("pipelines:logs", args=(pipeline.id,)),
        follow=True,
    )
    assert "task_1" in resp.content.decode(resp.charset)


@pytest.mark.django_db
def test_pipeline_log_failure(staff_client, mocker):
    pipeline = factories.PipelineFactory.create()
    mocker.patch(
        "dataworkspace.apps.datasets.pipelines.views.get_pipeline_logs",
        side_effect=RequestException(),
    )
    resp = staff_client.get(
        reverse("pipelines:logs", args=(pipeline.id,)),
        follow=True,
    )
    assert "There is a problem" in resp.content.decode(resp.charset)


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_query_fails_to_run(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={"table_name": "test", "sql": "SELECT * from doesnt_exist;"},
        follow=True,
    )
    assert b"Error running query" in resp.content
