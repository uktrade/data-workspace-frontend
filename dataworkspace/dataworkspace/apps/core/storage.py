import os
import uuid

import boto3
from botocore.exceptions import ClientError
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from django.urls import reverse


class S3FileStorage(FileSystemStorage):
    bucket = settings.AWS_UPLOADS_BUCKET
    base_prefix = 'uploaded-media'

    def get_s3_client(self):
        endpoint_url = settings.AWS_S3_ENDPOINT_URL
        client = boto3.client('s3', endpoint_url=endpoint_url)

        return client

    def _get_key(self, name):
        return os.path.join(self.base_prefix, self._location, name)

    def _save(self, name, content):
        client = self.get_s3_client()
        filename = f'{name}!{uuid.uuid4()}'
        key = self._get_key(filename)

        try:
            client.put_object(
                Body=content,
                Bucket=self.bucket,
                Key=key,
            )
        except ClientError as ex:
            raise Exception(
                'Error saving file: {}'.format(ex.response['Error']['Message'])
            )

        return filename

    def delete(self, name):
        client = self.get_s3_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=self._get_key(name))
        except ClientError:
            pass

    def url(self, name):
        return f'{reverse("uploaded-media")}?path={self._get_key(name)}'
