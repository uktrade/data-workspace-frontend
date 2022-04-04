import io

import pytest
from botocore.response import StreamingBody
from mock import mock

from dataworkspace.apps.your_files.constants import PostgresDataTypes
from dataworkspace.apps.your_files.utils import get_s3_csv_column_types


@pytest.mark.parametrize(
    "csv_content",
    [
        # Standard row
        b'col1,col2\nrow1-col1,1\n"row2\ncol1",2\nrow3-col1,3\n',
        # Contains BOM
        b'\xef\xbb\xbfcol1,col2\nrow1-col1,1\n"row2\ncol1",2\nrow3-col1,3\n',
        # Incomplete row
        b'col1,col2\n"row1-col1",1\n"row2\ncol1",2\n"row3\ncol\n1"',
    ],
)
@mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
def test_s3_csv_column_types(mock_client, csv_content):
    mock_client().head_object.return_value = {"ContentType": "text/csv"}
    mock_client().get_object.return_value = {
        "ContentType": "text/plain",
        "ContentLength": len(csv_content),
        "Body": StreamingBody(io.BytesIO(csv_content), len(csv_content)),
    }
    response = get_s3_csv_column_types("/a/path.csv")
    assert response == [
        {
            "header_name": "col1",
            "column_name": "col1",
            "data_type": PostgresDataTypes.TEXT,
            "sample_data": ["row1-col1", "row2\ncol1"],
        },
        {
            "header_name": "col2",
            "column_name": "col2",
            "data_type": PostgresDataTypes.INTEGER,
            "sample_data": ["1", "2"],
        },
    ]
