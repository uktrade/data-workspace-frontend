import logging
import os
import uuid

import boto3
import requests
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadhandler import UploadFileException
from django.db.models.fields.files import FieldFile
from django.urls import reverse

logger = logging.getLogger("app")


class AntiVirusServiceErrorException(UploadFileException):
    pass


class ClamAVResponse:
    def __init__(self, json_response):
        self.malware = json_response["malware"]
        self.reason = json_response.get("reason", "")


def _upload_to_clamav(file: File) -> ClamAVResponse:
    clamav_url = settings.CLAMAV_URL
    clamav_user = settings.CLAMAV_USER
    clamav_password = settings.CLAMAV_PASSWORD

    logger.debug("post to clamav %s", clamav_url)
    response = requests.post(clamav_url, auth=(clamav_user, clamav_password), files={"file": file})
    response.raise_for_status()

    clamav_response = ClamAVResponse(response.json())

    return clamav_response


class S3FileStorage(FileSystemStorage):
    bucket = settings.AWS_UPLOADS_BUCKET
    base_prefix = "uploaded-media"

    @staticmethod
    def _get_client():
        if settings.S3_LOCAL_ENDPOINT_URL:
            logger.info("using local S3 endpoint %s", settings.S3_LOCAL_ENDPOINT_URL)
            return boto3.client("s3", endpoint_url=settings.S3_LOCAL_ENDPOINT_URL)

        return boto3.client("s3")

    def _get_key(self, name):
        return os.path.join(self.base_prefix, self._location, name)

    @staticmethod
    def _av_check(name: str, content: File):
        logger.debug("S3FileStorageWithClamAV av check %s", name)

        clamav_response = _upload_to_clamav(content)

        if clamav_response.malware:
            msg = f"Virus found in {content.name} identified as {clamav_response.reason}"
            logger.error(msg)
            raise AntiVirusServiceErrorException(msg)

        # rewinding the file object so that it can be re-read
        # without it, we can't call the av_scan _and_ s3 upload
        content.seek(0)

    def _save_to_s3(self, name, content):

        client = self._get_client()
        filename = f"{name}!{uuid.uuid4()}"
        key = self._get_key(filename)

        try:
            client.put_object(
                Body=content,
                Bucket=self.bucket,
                Key=key,
            )
        except ClientError as ex:
            # pylint: disable=raise-missing-from
            raise Exception("Error saving file: {}".format(ex.response["Error"]["Message"]))

        return filename

    def _save(self, name, content):
        if not settings.DEBUG:
            self._av_check(name, content)
        return self._save_to_s3(name, content)

    def delete(self, name):
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=self._get_key(name))
        except ClientError:
            pass

    def url(self, name):
        return f'{reverse("uploaded-media")}?path={self._get_key(name)}'


def malware_file_validator(file: FieldFile):
    clamav_response = _upload_to_clamav(file)

    if clamav_response.malware:
        msg = f"Virus found in {file.name}"
        logger.error(msg)
        raise ValidationError(msg, code="virus_found", params={"value": file})
