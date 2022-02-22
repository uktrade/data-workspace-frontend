import datetime
from urllib.parse import urlencode

import botocore
import pytest
import requests_mock
from django.urls import reverse
from freezegun import freeze_time
from mock import mock

from dataworkspace.apps.your_files.models import UploadedTable


class TestCreateTableViews:
    def test_get_with_csv_file(self, client):
        response = client.get(
            reverse("your-files:create-table-confirm") + "?path=user/federated/abc/i-am-a.csv"
        )
        assert response.status_code == 200
        assert "You can create a table from i-am-a.csv" in response.content.decode(
            response.charset
        )

    def test_get_without_csv_file(self, client):
        response = client.get(reverse("your-files:create-table-confirm"))
        assert response.status_code == 400

    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_invalid_file_type(self, mock_get_s3_prefix, client):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={"path": "not-a-csv.txt"},
            follow=True,
        )
        assert "We can’t process your CSV file" in response.content.decode("utf-8")

    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_unauthorised_file(self, mock_get_s3_prefix, client):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={"path": "user/federated/def/a-csv.csv"},
            follow=True,
        )
        assert "We can’t process your CSV file" in response.content.decode("utf-8")

    @mock.patch("dataworkspace.apps.datasets.views.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_non_existent_file(self, mock_get_s3_prefix, mock_boto_client, client):
        mock_boto_client().head_object.side_effect = [
            botocore.exceptions.ClientError(
                error_response={"Error": {"Message": "it failed"}},
                operation_name="head_object",
            )
        ]
        mock_get_s3_prefix.return_value = "user/federated/abc"
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={"path": "user/federated/abc/a-csv.csv"},
            follow=True,
        )
        assert "We can’t process your CSV file" in response.content.decode("utf-8")

    @mock.patch("dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    @mock.patch("dataworkspace.apps.your_files.views.get_schema_for_user")
    def test_trigger_failed(
        self,
        mock_get_schema_for_user,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        client,
    ):
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = [
            {
                "header_name": "Field 1",
                "column_name": "field1",
                "data_type": "text",
                "sample_data": ["a", "b", "c"],
            }
        ]

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        with requests_mock.Mocker() as rmock:
            rmock.post(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline/dag_runs",
                status_code=500,
            )
            response = client.post(
                f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}',
                data={
                    "path": "user/federated/abc/a-csv.csv",
                    "table_name": "test_table",
                    "schema": "test_schema",
                    "field1": "integer",
                },
                follow=True,
            )

        assert "We can’t process your CSV file" in response.content.decode("utf-8")

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    @mock.patch("dataworkspace.apps.your_files.views.get_schema_for_user")
    def test_success(
        self,
        mock_get_schema_for_user,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        client,
    ):
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = [
            {
                "header_name": "Field 1",
                "column_name": "field1",
                "data_type": "text",
                "sample_data": [1, 2, 3],
            }
        ]
        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        response = client.post(
            f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_schema",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"Validating" in response.content
        mock_get_column_types.assert_called_with("user/federated/abc/a-csv.csv")
        mock_copy_file.assert_called_with(
            "user/federated/abc/a-csv.csv",
            "data-flow-imports/user/federated/abc/a-csv.csv",
        )
        mock_trigger_dag.assert_called_with(
            {
                "db_role": "test_schema",
                "file_path": "data-flow-imports/user/federated/abc/a-csv.csv",
                "schema_name": "test_schema",
                "table_name": "a_csv",
                "column_definitions": [
                    {
                        "header_name": "Field 1",
                        "column_name": "field1",
                        "data_type": "integer",
                        "sample_data": [1, 2, 3],
                    }
                ],
            },
            "DataWorkspaceS3ImportPipeline",
            "test_schema-a_csv-2021-01-01T01:01:01",
        )

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_confirm_schema_with_teams(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = [
            {"name": "TeamA", "schema_name": "_team_a_schema"},
            {"name": "TeamB", "schema_name": "_team_b_schema"},
        ]

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        response = client.post(
            f'{reverse("your-files:create-table-confirm-schema")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_schema",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"test_schema (your private schema)" in response.content
        assert b"_team_a_schema (TeamA shared schema)" in response.content
        assert b"_team_b_schema (TeamB shared schema)" in response.content

        # Only admins can create new schemas
        assert b"Create new schema" not in response.content

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_confirm_schema_without_teams(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = []

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        response = client.post(
            f'{reverse("your-files:create-table-confirm-schema")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_schema",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"test_schema (your private schema)" in response.content
        assert b"shared schema" not in response.content

        # Only admins can create new schemas
        assert b"Create new schema" not in response.content

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_confirm_schema_staff_user(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        staff_client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = []

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        response = staff_client.post(
            f'{reverse("your-files:create-table-confirm-schema")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_schema",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"public" in response.content
        assert b"dit" in response.content
        assert b"test_schema (your private schema)" in response.content
        assert b"shared schema" not in response.content

        # Admins should be able to create a new schema
        assert b"Create new schema" in response.content

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_staff_user_create_new_schema(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        staff_client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = []

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_schema",
        }
        response = staff_client.post(
            f'{reverse("your-files:create-table-confirm-schema")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "new",
                "table_name": "a_csv",
                "field1": "integer",
            },
        )
        assert response.status_code == 302
        assert reverse("your-files:create-schema") in response.get("location")

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_staff_user_create_new_schema_success(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        staff_client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = []

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
        }
        response = staff_client.post(
            f'{reverse("your-files:create-schema")}?{urlencode(params)}',
            data={
                "schema": "new",
            },
        )

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "schema": "new",
            "team": "new",
            "table_name": "test_table",
        }
        assert response.status_code == 302
        assert (
            response.get("location")
            == f'{reverse("your-files:create-table-confirm-name")}?{urlencode(params)}'
        )

    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_staff_user_create_new_schema_fail(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_all_schemas,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        staff_client,
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = []

        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
        }
        response = staff_client.post(
            f'{reverse("your-files:create-schema")}?{urlencode(params)}',
            data={
                "schema": "public",
            },
        )
        assert response.status_code == 200
        assert b"schema &quot;public&quot; already exists" in response.content

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.views.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_success_team_schema(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        client,
    ):
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = [
            {"name": "TestTeam", "schema_name": "test_team_schema"},
        ]
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = [
            {
                "header_name": "Field 1",
                "column_name": "field1",
                "data_type": "text",
                "sample_data": [1, 2, 3],
            }
        ]
        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "test_team_schema",
        }
        response = client.post(
            f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_team_schema",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"Validating" in response.content
        mock_get_column_types.assert_called_with("user/federated/abc/a-csv.csv")
        mock_copy_file.assert_called_with(
            "user/federated/abc/a-csv.csv",
            "data-flow-imports/user/federated/abc/a-csv.csv",
        )
        mock_trigger_dag.assert_called_with(
            {
                "db_role": "test_team_schema",
                "file_path": "data-flow-imports/user/federated/abc/a-csv.csv",
                "schema_name": "test_team_schema",
                "table_name": "a_csv",
                "column_definitions": [
                    {
                        "header_name": "Field 1",
                        "column_name": "field1",
                        "data_type": "integer",
                        "sample_data": [1, 2, 3],
                    }
                ],
            },
            "DataWorkspaceS3ImportPipeline",
            "test_team_schema-a_csv-2021-01-01T01:01:01",
        )

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.get_all_schemas")
    @mock.patch("dataworkspace.apps.your_files.views.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.views.get_team_schemas_for_user")
    @mock.patch("dataworkspace.apps.your_files.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_success_all_schemas(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        mock_get_all_schemas,
        staff_client,
    ):
        mock_get_all_schemas.return_value = ["public", "dit"]
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = [
            {"name": "TestTeam", "schema_name": "test_team_schema"},
        ]
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = [
            {
                "header_name": "Field 1",
                "column_name": "field1",
                "data_type": "text",
                "sample_data": [1, 2, 3],
            }
        ]
        params = {
            "path": "user/federated/abc/a-csv.csv",
            "table_name": "test_table",
            "schema": "public",
        }
        response = staff_client.post(
            f'{reverse("your-files:create-table-confirm-data-types")}?{urlencode(params)}',
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "public",
                "table_name": "a_csv",
                "field1": "integer",
            },
            follow=True,
        )
        assert b"Validating" in response.content
        mock_get_column_types.assert_called_with("user/federated/abc/a-csv.csv")
        mock_copy_file.assert_called_with(
            "user/federated/abc/a-csv.csv",
            "data-flow-imports/user/federated/abc/a-csv.csv",
        )
        mock_trigger_dag.assert_called_with(
            {
                "file_path": "data-flow-imports/user/federated/abc/a-csv.csv",
                "schema_name": "public",
                "table_name": "a_csv",
                "column_definitions": [
                    {
                        "header_name": "Field 1",
                        "column_name": "field1",
                        "data_type": "integer",
                        "sample_data": [1, 2, 3],
                    }
                ],
            },
            "DataWorkspaceS3ImportPipeline",
            "public-a_csv-2021-01-01T01:01:01",
        )

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.forms.get_schema_for_user")
    @mock.patch("dataworkspace.apps.your_files.forms.get_team_schemas_for_user")
    def test_invalid_schema(
        self,
        mock_get_team_schemas_for_user,
        mock_get_schema_for_user,
        client,
    ):
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_team_schemas_for_user.return_value = [
            {"name": "TestTeam", "schema_name": "test_team_schema"},
        ]
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "_user_xxxxxx",
                "table_name": "a csv with a space",
            },
            follow=True,
        )
        assert response.status_code == 404

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_invalid_table_name(
        self, mock_get_s3_prefix, mock_boto_client, mock_get_column_types, client
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = {"field1": "varchar"}
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "_user_40e80e4e",
                "table_name": "a csv with a space",
            },
            follow=True,
        )
        assert b"Table names can contain only letters, numbers and underscores" in response.content

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    def test_table_name_too_long(
        self, mock_get_s3_prefix, mock_boto_client, mock_get_column_types, client
    ):
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = {"field1": "varchar"}
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "_user_40e80e4e",
                "table_name": "a_very_long_table_name_which_is_over_fourty_two_chars",
            },
            follow=True,
        )
        assert b"Table names must be no longer than 42 characters long" in response.content

    @freeze_time("2021-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.trigger_dataflow_dag")
    @mock.patch("dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket")
    @mock.patch("dataworkspace.apps.your_files.views.get_s3_csv_column_types")
    @mock.patch("dataworkspace.apps.your_files.utils.boto3.client")
    @mock.patch("dataworkspace.apps.your_files.forms.get_s3_prefix")
    @mock.patch("dataworkspace.apps.your_files.views.get_schema_for_user")
    def test_table_exists_override(
        self,
        mock_get_schema_for_user,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        client,
    ):
        mock_get_schema_for_user.return_value = "test_schema"
        mock_get_s3_prefix.return_value = "user/federated/abc"
        mock_get_column_types.return_value = [
            {
                "header_name": "Field 1",
                "column_name": "field1",
                "data_type": "text",
                "sample_data": ["a", "b", "c"],
            }
        ]
        response = client.post(
            reverse("your-files:create-table-confirm-name"),
            data={
                "path": "user/federated/abc/a-csv.csv",
                "schema": "test_schema",
                "table_name": "a_csv",
                "force_overwrite": True,
            },
            follow=True,
        )
        assert b"Choose data types for a_csv" in response.content

    @pytest.mark.parametrize(
        "url, success_text",
        (
            ("your_files:create-table-validating", b"Validating"),
            ("your_files:create-table-creating-table", b"Creating temporary table"),
            ("your_files:create-table-ingesting", b"Inserting data"),
            ("your_files:create-table-renaming-table", b"Renaming temporary table"),
            ("your_files:create-table-success", b"Table created"),
        ),
    )
    @pytest.mark.parametrize(
        "params, status_code",
        (
            ({}, 400),
            ({"filename": "test.csv"}, 400),
            ({"filename": "test.csv", "schema": "test"}, 400),
            (
                {
                    "filename": "test.csv",
                    "schema": "test",
                    "table_name": "table",
                },
                400,
            ),
            (
                {
                    "filename": "test.csv",
                    "schema": "test",
                    "table_name": "table",
                    "execution_date": "2021-01-01T00:00:00",
                },
                200,
            ),
        ),
    )
    def test_steps(self, url, success_text, params, status_code, client):
        response = client.get(f"{reverse(url)}?{urlencode(params)}")
        assert response.status_code == status_code
        if status_code == 200:
            assert success_text in response.content
        if success_text == "Table created":
            assert len(UploadedTable.objects.all()) == 1
            assert UploadedTable.objects.all()[0].schema == "test"
            assert UploadedTable.objects.all()[0].table_name == "table"
            assert UploadedTable.objects.all()[0].data_flow_execution_date == datetime.datetime(
                2021, 1, 1
            )

    @pytest.mark.parametrize("status_code", (500, 404))
    def test_dag_status_invalid(self, status_code, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}',
                status_code=status_code,
            )
            response = client.get(
                reverse("your_files:create-table-dag-status", args=(execution_date,))
            )
            assert response.status_code == status_code

    def test_dag_status(self, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}',
                json={"state": "success"},
            )
            response = client.get(
                reverse("your_files:create-table-dag-status", args=(execution_date,))
            )
            assert response.status_code == 200
            assert response.json() == {"state": "success"}

    @pytest.mark.parametrize("status_code", (500, 404))
    def test_task_status_invalid(self, status_code, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        task_id = "task-id"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}/tasks/{task_id}',
                status_code=status_code,
            )
            response = client.get(
                reverse(
                    "your_files:create-table-task-status",
                    args=(execution_date, task_id),
                )
            )
            assert response.status_code == status_code

    def test_task_status(self, client):
        execution_date = "02-05T13:33:49.266040+00:00"
        task_id = "task-id"
        with requests_mock.Mocker() as rmock:
            # pylint: disable=use-maxsplit-arg
            rmock.get(
                "https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline"
                f'/dag_runs/{execution_date.split("+")[0]}/tasks/{task_id}',
                json={"state": "success"},
            )
            response = client.get(
                reverse(
                    "your_files:create-table-task-status",
                    args=(execution_date, task_id),
                )
            )
            assert response.status_code == 200
            assert response.json() == {"state": "success"}


class TestRestoreTableViews:
    @freeze_time("2022-01-01 01:01:01")
    @mock.patch("dataworkspace.apps.your_files.views.trigger_dataflow_dag")
    def test_restore_table_view(
        self, mock_trigger_dataflow_dag, dataset_db_with_swap_table, staff_client
    ):
        mock_trigger_dataflow_dag.return_value = {"execution_date": "2022-01-01"}

        t = UploadedTable.objects.create(
            schema="public",
            table_name="dataset_test",
            data_flow_execution_date=datetime.datetime(2022, 1, 1),
        )

        response = staff_client.get(reverse("your_files:restore-table", args=(t.id,)))

        assert b"Restore table created on Jan. 1, 2022, midnight" in response.content
        assert b"test_2" in response.content
        assert (
            b"Overwrite existing table public.dataset_test with the above table?"
            in response.content
        )

        response = staff_client.post(reverse("your_files:restore-table", args=(t.id,)))

        mock_trigger_dataflow_dag.assert_called_with(
            {
                "ts_nodash": "20220101t000000",
                "schema_name": "public",
                "table_name": "dataset_test",
            },
            "DataWorkspaceRestoreTablePipeline",
            "restore-public-dataset_test-2022-01-01T01:01:01",
        )

        expected_params = {
            "execution_date": "2022-01-01",
            "task_name": "restore-swap-table-datasets_db",
        }
        assert response.status_code == 302
        assert (
            response.get("location")
            == f'{reverse("your-files:restore-table-in-progress", args=(t.id,))}?{urlencode(expected_params)}'
        )
