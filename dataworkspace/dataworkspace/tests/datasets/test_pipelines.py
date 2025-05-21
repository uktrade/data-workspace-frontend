import pytest
from django.test import Client
from django.urls import reverse
from mock import mock

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data
from dataworkspace.apps.datasets.constants import PipelineScheduleType


@pytest.mark.django_db
@pytest.mark.parametrize(
    "table_name,expected_output,added_pipelines",
    (
        (
            "no_dot",
            "Table name must be lower case in the format schema.table or &quot;schema&quot;.&quot;table&quot;",
            0,
        ),
        (
            "CAPITAL.table",
            "Table name must be lower case in the format schema.table or &quot;schema&quot;.&quot;table&quot;",
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
        data={"type": "sql", "table_name": table_name, "schedule": "@yearly", "sql": "SELECT 1"},
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
            "schedule": "@monthly",
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
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@daily",
            "sql": "SELECT bar as 1;",
        },
        follow=True,
    )
    assert b"syntax error" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_single_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@monthly",
            "sql": "SELECT 1; SELECT 2;",
        },
        follow=True,
    )
    assert b"Enter a single statement" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_drop_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@weekly",
            "sql": "DROP TABLE foo;",
        },
        follow=True,
    )
    assert b"Only SELECT statements are supported" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_create_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@yearly",
            "sql": "CREATE TABLE foo (f1 int);",
        },
        follow=True,
    )
    assert b"Only SELECT statements are supported" in resp.content


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_custom_schedule_statement(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@custom",
            "custom_schedule": "",
            "sql": "SELECT * FROM foo;",
        },
        follow=True,
    )
    assert (
        b"selected in schedule field but custom schedule field was empty or invalid"
        in resp.content
    )


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_create_pipeline_validates_duplicate_column_names(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "type": "sql",
            "table_name": "test",
            "schedule": "@monthly",
            "sql": "SELECT 1 AS foo, 2 AS foo;",
        },
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
        data={
            "type": "sql",
            "table_name": pipeline.table_name,
            "schedule": "@daily",
            "sql": "SELECT 2",
        },
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
            "schedule": "@yearly",
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
            "schedule": "@daily",
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
            "schedule": "@monthly",
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


@mock.patch("dataworkspace.apps.datasets.pipelines.views.save_pipeline_to_dataflow")
def test_query_fails_to_run(mock_sync, staff_client):
    staff_client.post(reverse("admin:index"), follow=True)
    resp = staff_client.post(
        reverse("pipelines:create-sql"),
        data={
            "table_name": "test",
            "sql": "SELECT * from doesnt_exist;",
            "schedule": "@monthly",
        },
        follow=True,
    )
    assert b"Error running query" in resp.content


@pytest.mark.django_db
def test_superuser_can_see_pipelines():
    pipeline_1 = factories.PipelineFactory.create(type="sharepoint", table_name="schema.table_1")
    pipeline_2 = factories.PipelineFactory.create(type="sql", table_name="schema.table_2")

    user = factories.UserFactory.create(is_superuser=True)
    client = Client(**get_http_sso_data(user))

    resp = client.get(reverse("pipelines:index"))
    assert resp.status_code == 200

    content = resp.content.decode(resp.charset)
    assert "You do not have access to any pipelines." not in content
    assert "Add new pipeline" in content
    assert pipeline_1.table_name in content
    assert pipeline_2.table_name in content
    assert f'id="{ pipeline_1.table_name }"' in content
    assert f'id="{ pipeline_2.table_name }"' in content


@pytest.mark.parametrize(
    "schedule,custom_schedule,expected_value",
    [
        (PipelineScheduleType.ONCE, "", "Runs manually"),
        (PipelineScheduleType.DAILY, "", "Runs daily at midnight"),
        (PipelineScheduleType.WEEKLY, "", "Runs on Sundays at midnight"),
        (PipelineScheduleType.MONTHLY, "", "Runs on the first of every month at midnight"),
        (PipelineScheduleType.YEARLY, "", "Runs every January 1st at midnight"),
        (PipelineScheduleType.FRIDAYS, "", "Runs on Fridays at midnight"),
        (
            PipelineScheduleType.CUSTOM,
            "* 12 * 5 *",
            "Runs every minute, between 12:00\xa0PM and 12:59\xa0PM, only in May",
        ),
    ],
)
@pytest.mark.django_db
def test_superuser_can_see_schedules(schedule, custom_schedule, expected_value):
    factories.PipelineFactory.create(
        type="sharepoint",
        table_name="schema.table_1",
        schedule=schedule,
        custom_schedule=custom_schedule,
    )

    user = factories.UserFactory.create(is_superuser=True)
    client = Client(**get_http_sso_data(user))

    resp = client.get(reverse("pipelines:index"))
    assert resp.status_code == 200

    content = resp.content.decode(resp.charset)
    assert expected_value in content


@pytest.mark.django_db
def test_non_superuser_cannot_see_pipelines():
    pipeline_1 = factories.PipelineFactory.create(type="sharepoint", table_name="schema.table_1")
    pipeline_2 = factories.PipelineFactory.create(type="sql", table_name="schema.table_2")

    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    resp = client.get(reverse("pipelines:index"))
    assert resp.status_code == 200

    content = resp.content.decode(resp.charset)
    assert "You do not have access to any pipelines." in content
    assert "Add new pipeline" not in content
    assert pipeline_1.table_name not in content
    assert pipeline_2.table_name not in content


def set_catalogue_editor(source_dataset, user):
    source_dataset.data_catalogue_editors.add(user)


def set_iam(source_dataset, user):
    source_dataset.information_asset_manager = user


def set_iao(source_dataset, user):
    source_dataset.information_asset_owner = user


def escape_quote_html(string):
    return string.replace('"', "&quot;")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "give_user_management_access_to_dataset",
    [
        set_catalogue_editor,
        set_iam,
        set_iao,
    ],
)
@pytest.mark.parametrize(
    "quote",
    [
        lambda schema, table: f"{schema}.{table}",
        lambda schema, table: f'{schema}."{table}"',
        lambda schema, table: f'"{schema}".{table}',
        lambda schema, table: f'"{schema}"."{table}"',
    ],
)
def test_non_admin_user_can_only_see_their_own_sharepoint_and_sql_pipelines(
    metadata_db,
    give_user_management_access_to_dataset,
    quote,
):
    pipeline_1 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_1")
    )
    pipeline_2 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_2")
    )
    pipeline_3 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_3")
    )
    pipeline_4 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_4")
    )

    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    source_dataset = factories.MasterDataSetFactory.create()
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_1"
    )
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_3"
    )
    give_user_management_access_to_dataset(source_dataset, user)
    source_dataset.save()

    resp = client.get(reverse("pipelines:index"))
    assert resp.status_code == 200

    content = resp.content.decode(resp.charset)
    assert "You do not have access to any pipelines." not in content
    assert "Add new pipeline" not in content
    assert escape_quote_html(pipeline_1.table_name) in content
    assert f'id="{ escape_quote_html(pipeline_1.table_name) }"' in content
    assert escape_quote_html(pipeline_2.table_name) not in content
    assert escape_quote_html(pipeline_3.table_name) in content
    assert f'id="{ escape_quote_html(pipeline_3.table_name) }"' in content
    assert escape_quote_html(pipeline_4.table_name) not in content

    assert "Edit" not in content
    assert "Delete" not in content
    assert "View pipeline " not in content
    assert ">Run" in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "give_user_management_access_to_dataset",
    [
        set_catalogue_editor,
        set_iam,
        set_iao,
    ],
)
@pytest.mark.parametrize(
    "quote",
    [
        lambda schema, table: f"{schema}.{table}",
        lambda schema, table: f'{schema}."{table}"',
        lambda schema, table: f'"{schema}".{table}',
        lambda schema, table: f'"{schema}"."{table}"',
    ],
)
@mock.patch("dataworkspace.apps.datasets.pipelines.views.run_pipeline")
def test_non_admin_user_can_run_their_own_sharepoint_and_sql_pipelines(
    mock_run,
    metadata_db,
    give_user_management_access_to_dataset,
    quote,
):
    pipeline_1 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_1")
    )
    pipeline_2 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_2")
    )
    pipeline_3 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_3")
    )
    pipeline_4 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_4")
    )

    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    source_dataset = factories.MasterDataSetFactory.create()
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_1"
    )
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_3"
    )
    give_user_management_access_to_dataset(source_dataset, user)
    source_dataset.save()

    resp_1 = client.post(reverse("pipelines:run", args=(pipeline_1.id,)), follow=True)
    assert "Pipeline triggered successfully" in resp_1.content.decode(resp_1.charset)

    resp_2 = client.post(reverse("pipelines:run", args=(pipeline_2.id,)), follow=True)
    assert "Pipeline triggered successfully" not in resp_2.content.decode(resp_2.charset)

    resp_3 = client.post(reverse("pipelines:run", args=(pipeline_3.id,)), follow=True)
    assert "Pipeline triggered successfully" in resp_3.content.decode(resp_3.charset)

    resp_4 = client.post(reverse("pipelines:run", args=(pipeline_4.id,)), follow=True)
    assert "Pipeline triggered successfully" not in resp_4.content.decode(resp_4.charset)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "give_user_management_access_to_dataset",
    [
        set_catalogue_editor,
        set_iam,
        set_iao,
    ],
)
@pytest.mark.parametrize(
    "quote",
    [
        lambda schema, table: f"{schema}.{table}",
        lambda schema, table: f'{schema}."{table}"',
        lambda schema, table: f'"{schema}".{table}',
        lambda schema, table: f'"{schema}"."{table}"',
    ],
)
@mock.patch("dataworkspace.apps.datasets.pipelines.views.stop_pipeline")
def test_non_admin_user_can_stop_their_own_sharepoint_and_sql_pipelines(
    mock_stop,
    metadata_db,
    give_user_management_access_to_dataset,
    quote,
):
    pipeline_1 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_1")
    )
    pipeline_2 = factories.PipelineFactory.create(
        type="sharepoint", table_name=quote("schema", "table_2")
    )
    pipeline_3 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_3")
    )
    pipeline_4 = factories.PipelineFactory.create(
        type="sql", table_name=quote("schema", "table_4")
    )

    user = factories.UserFactory.create(is_superuser=False)
    client = Client(**get_http_sso_data(user))

    source_dataset = factories.MasterDataSetFactory.create()
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_1"
    )
    factories.SourceTableFactory(
        dataset=source_dataset, database=metadata_db, schema="schema", table="table_3"
    )
    give_user_management_access_to_dataset(source_dataset, user)
    source_dataset.save()

    resp_1 = client.post(reverse("pipelines:stop", args=(pipeline_1.id,)), follow=True)
    assert "Pipeline stopped successfully" in resp_1.content.decode(resp_1.charset)

    resp_2 = client.post(reverse("pipelines:stop", args=(pipeline_2.id,)), follow=True)
    assert "Pipeline stopped successfully" not in resp_2.content.decode(resp_2.charset)

    resp_3 = client.post(reverse("pipelines:stop", args=(pipeline_3.id,)), follow=True)
    assert "Pipeline stopped successfully" in resp_3.content.decode(resp_3.charset)

    resp_4 = client.post(reverse("pipelines:stop", args=(pipeline_4.id,)), follow=True)
    assert "Pipeline stopped successfully" not in resp_4.content.decode(resp_4.charset)
