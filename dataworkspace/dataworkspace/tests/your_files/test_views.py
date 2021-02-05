from urllib.parse import urlencode

import botocore
import pytest
import requests_mock
from django.conf import settings
from django.urls import reverse
from freezegun import freeze_time
from mock import mock
from waffle.testutils import override_flag


class TestCreateTableViews:
    url = reverse('your-files:create-table')

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    def test_get_with_csv_file(self, client):
        response = client.get(self.url + "?path=user/federated/abc/i-am-a.csv")
        assert response.status_code == 200
        assert "Create a table from i-am-a.csv" in response.content.decode(
            response.charset
        )

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_invalid_file_type(self, mock_get_s3_prefix, client):
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        response = client.post(self.url, data={'path': 'not-a-csv.txt'}, follow=True,)
        assert b'We can\'t process your CSV file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_unauthorised_file(self, mock_get_s3_prefix, client):
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        response = client.post(
            self.url, data={'path': 'user/federated/def/a-csv.csv'}, follow=True,
        )
        assert b'We can\'t process your CSV file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @mock.patch('dataworkspace.apps.datasets.views.boto3.client')
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_non_existent_file(self, mock_get_s3_prefix, mock_boto_client, client):
        mock_boto_client().head_object.side_effect = [
            botocore.exceptions.ClientError(
                error_response={'Error': {'Message': 'it failed'}},
                operation_name='head_object',
            )
        ]
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        response = client.post(
            self.url, data={'path': 'user/federated/abc/a-csv.csv'}, follow=True,
        )
        assert b'We can\'t process your CSV file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @mock.patch('dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket')
    @mock.patch('dataworkspace.apps.your_files.views.get_s3_csv_column_types')
    @mock.patch('dataworkspace.apps.your_files.utils.boto3.client')
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_trigger_failed(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        client,
    ):
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        mock_get_column_types.return_value = {'field1': 'varchar'}
        with requests_mock.Mocker() as rmock:
            rmock.post(
                'https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline/dag_runs',
                status_code=500,
            )
            response = client.post(
                self.url,
                data={'path': 'user/federated/abc/not-a-csv.csv'},
                follow=True,
            )
        assert b'We can\'t process your CSV file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @freeze_time('2021-01-01 01:01:01')
    @mock.patch('dataworkspace.apps.your_files.views.trigger_dataflow_dag')
    @mock.patch('dataworkspace.apps.your_files.views.copy_file_to_uploads_bucket')
    @mock.patch('dataworkspace.apps.your_files.views.get_s3_csv_column_types')
    @mock.patch('dataworkspace.apps.your_files.utils.boto3.client')
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_success(
        self,
        mock_get_s3_prefix,
        mock_boto_client,
        mock_get_column_types,
        mock_copy_file,
        mock_trigger_dag,
        client,
    ):
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        mock_get_column_types.return_value = {'field1': 'varchar'}
        response = client.post(
            self.url, data={'path': 'user/federated/abc/a-csv.csv'}, follow=True,
        )
        assert b'Validating a-csv.csv' in response.content
        mock_get_column_types.assert_called_with('user/federated/abc/a-csv.csv')
        mock_copy_file.assert_called_with(
            'user/federated/abc/a-csv.csv',
            'data-flow-imports/user/federated/abc/a-csv.csv',
        )
        mock_trigger_dag.assert_called_with(
            'data-flow-imports/user/federated/abc/a-csv.csv',
            '_user_40e80e4e',
            'a_csv',
            {'field1': 'varchar'},
            '_user_40e80e4e-a_csv-2021-01-01T01:01:01',
        )

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @pytest.mark.parametrize(
        'url, success_text',
        (
            ('your_files:create-table-validating', b'Validating test.csv'),
            ('your_files:create-table-ingesting', b'Importing test.csv'),
            ('your_files:create-table-success', b'Table created'),
        ),
    )
    @pytest.mark.parametrize(
        'params, status_code',
        (
            ({}, 400),
            ({'filename': 'test.csv'}, 400),
            ({'filename': 'test.csv', 'schema': 'test'}, 400),
            ({'filename': 'test.csv', 'schema': 'test', 'table_name': 'table'}, 400),
            (
                {
                    'filename': 'test.csv',
                    'schema': 'test',
                    'table_name': 'table',
                    'execution_date': '2021-01-01',
                },
                200,
            ),
        ),
    )
    def test_steps(self, url, success_text, params, status_code, client):
        response = client.get(f'{reverse(url)}?{urlencode(params)}')
        assert response.status_code == status_code
        if status_code == 200:
            assert success_text in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @pytest.mark.parametrize('status_code', (500, 404))
    def test_dag_status_invalid(self, status_code, client):
        execution_date = '02-05T13:33:49.266040+00:00'
        with requests_mock.Mocker() as rmock:
            rmock.get(
                f'https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline/dag_runs/{execution_date}',
                status_code=status_code,
            )
            response = client.get(
                reverse('your_files:create-table-status', args=(execution_date,))
            )
            assert response.status_code == status_code

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    def test_dag_status(self, client):
        execution_date = '02-05T13:33:49.266040+00:00'
        with requests_mock.Mocker() as rmock:
            rmock.get(
                f'https://data-flow/api/experimental/dags/DataWorkspaceS3ImportPipeline/dag_runs/{execution_date}',
                json={'state': 'success'},
            )
            response = client.get(
                reverse('your_files:create-table-status', args=(execution_date,))
            )
            assert response.status_code == 200
            assert response.json() == {'state': 'success'}
