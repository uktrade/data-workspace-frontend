import logging
import os
import uuid

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.urls import reverse

from dataworkspace.apps.core.boto3_utils import get_boto3_s3_client

logger = logging.getLogger(__name__)


class S3FileStorage(FileSystemStorage):
    bucket = settings.AWS_UPLOADS_BUCKET
    base_prefix = 'uploaded-media'


    def _get_key(self, name):
        key =  os.path.join(self.base_prefix, self._location, name)
        logger.debug(key)
        return key

    def _save(self, name, content):
        client = get_boto3_s3_client()
        filename = f'{name}!{uuid.uuid4()}'
        key = self._get_key(filename)

        try:
            client.put_object(
                Body=content, Bucket=self.bucket, Key=key,
            )
        except ClientError as ex:
            raise Exception(
                'Error saving file: {}'.format(ex.response['Error']['Message'])
            )

        return filename

    def delete(self, name):
        client = get_boto3_s3_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=self._get_key(name))
        except ClientError:
            pass

    def url(self, name):
        url = f'{reverse("uploaded-media")}?path={self._get_key(name)}'
        logger.debug('media_url %s', url)
        return url
