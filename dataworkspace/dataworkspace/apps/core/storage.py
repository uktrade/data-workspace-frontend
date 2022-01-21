import os
import uuid

import logging

import boto3
from botocore.exceptions import ClientError
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from django.urls import reverse

logger = logging.getLogger("app")


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

    def _save(self, name, content):
        client = self._get_client()
        filename = f"{name}!{uuid.uuid4()}"
        key = self._get_key(filename)
        logger.info("S3FileStorage save %s", key)

        try:
            client.put_object(
                Body=content,
                Bucket=self.bucket,
                Key=key,
            )
        except ClientError as ex:
            # pylint: disable=raise-missing-from
            raise Exception(
                "Error saving file: {}".format(ex.response["Error"]["Message"])
            )

        return filename

    def delete(self, name):
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=self._get_key(name))
        except ClientError:
            pass

    def url(self, name):
        return f'{reverse("uploaded-media")}?path={self._get_key(name)}'


class S3FileStorageWithClamAV(S3FileStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        logger.info("using S3FileStorageWithClamAV")

    def _av_check(self, name):
        # TODO - https://github.com/uktrade/dit-clamav-rest/blob/master/client-examples/example.py
        # Perhaps review chunking uploads?
        logger.info("S3FileStorageWithClamAV av check %s", name)
        pass

    def _save(self, name, content: bytes):
        logger.info("S3FileStorageWithClamAV save")
        self._av_check(name)
        return super()._save(name, content)
