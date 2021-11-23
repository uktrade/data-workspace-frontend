import mock

from dataworkspace.apps.core.storage import S3FileStorage


@mock.patch("dataworkspace.apps.core.storage.uuid.uuid4")
@mock.patch("dataworkspace.apps.core.storage.boto3.client")
def test_file_save(mock_client, mock_uuid):
    mock_uuid.return_value = "xxx-xxx"
    fs = S3FileStorage(location="a-location")
    assert fs.save("a-filename.txt", b"") == "a-filename.txt!xxx-xxx"
    mock_client().put_object.assert_called_once_with(
        Body=mock.ANY,
        Bucket="an-upload-bucket",
        Key="uploaded-media/a-location/a-filename.txt!xxx-xxx",
    )
    assert (
        fs.url("a-filename.txt!xxx-xxx")
        == "/media?path=uploaded-media/a-location/a-filename.txt!xxx-xxx"
    )
