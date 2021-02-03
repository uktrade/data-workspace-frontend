import botocore
import requests_mock
from django.conf import settings
from django.urls import reverse
from mock import mock
from waffle.testutils import override_flag


class TestCreateTableView:
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
        response = client.post(
            self.url, data={'path': 'user/federated/abc/not-a-csv.txt'}, follow=True,
        )
        assert b'An error occurred while processing your file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
    @mock.patch('dataworkspace.apps.your_files.forms.get_s3_prefix')
    def test_unauthorised_file(self, mock_get_s3_prefix, client):
        mock_get_s3_prefix.return_value = 'user/federated/abc'
        response = client.post(
            self.url, data={'path': 'user/federated/def/a-csv.csv'}, follow=True,
        )
        assert b'An error occurred while processing your file' in response.content

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
        assert b'An error occurred while processing your file' in response.content

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
            assert b'An error occurred while processing your file' in response.content

    @override_flag(settings.YOUR_FILES_CREATE_TABLE_FLAG, active=True)
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
        assert b'Table created' in response.content
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
        )
