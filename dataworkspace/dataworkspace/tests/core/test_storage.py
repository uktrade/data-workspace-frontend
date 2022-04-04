import io

import mock
import pytest
from django.test import override_settings
from dataworkspace.apps.core.storage import (
    S3FileStorage,
    ClamAVResponse,
    AntiVirusServiceErrorException,
)


@mock.patch("dataworkspace.apps.core.storage.uuid.uuid4")
@mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
@mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
def test_file_save(mock_upload_to_clamav, mock_client, mock_uuid):
    mock_upload_to_clamav.return_value = ClamAVResponse({"malware": False})
    mock_uuid.return_value = "xxx-xxx"
    fs = S3FileStorage(location="a-location")

    stream = io.BytesIO(b"")
    assert fs.save("a-filename.txt", stream) == "a-filename.txt!xxx-xxx"
    mock_client().put_object.assert_called_once_with(
        Body=mock.ANY,
        Bucket="an-upload-bucket",
        Key="uploaded-media/a-location/a-filename.txt!xxx-xxx",
    )
    assert (
        fs.url("a-filename.txt!xxx-xxx")
        == "/media?path=uploaded-media/a-location/a-filename.txt!xxx-xxx"
    )


@override_settings(LOCAL=False)
@mock.patch("dataworkspace.apps.core.storage.uuid.uuid4")
@mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
@mock.patch("dataworkspace.apps.core.storage._upload_to_clamav")
def test_file_save_throws_exception_when_virus_found(
    mock_upload_to_clamav, mock_client, mock_uuid
):
    clamav_response_dict = {"malware": True, "reason": "malware description"}
    mock_upload_to_clamav.return_value = ClamAVResponse(clamav_response_dict)
    mock_uuid.return_value = "xxx-xxx"

    with pytest.raises(AntiVirusServiceErrorException):
        fs = S3FileStorage(location="a-location")

        stream = io.BytesIO(b"")
        fs.save("a-filename.txt", stream)

        mock_client().put_object.assert_not_called()
