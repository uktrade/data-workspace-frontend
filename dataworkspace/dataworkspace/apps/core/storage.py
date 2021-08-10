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

    def _get_key(self, name):
        return os.path.join(self.base_prefix, self._location, name)

    def _save(self, name, content):
        client = boto3.client(
            's3',
            endpoint_url='http://host.docker.internal:9000',
            aws_access_key_id='AKIAV3ON3AJYFQS6BJ3B',
            aws_secret_access_key='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',
        )
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
        client = boto3.client('s3')
        try:
            client.delete_object(Bucket=self.bucket, Key=self._get_key(name))
        except ClientError:
            pass

    def url(self, name):
        return f'{reverse("uploaded-media")}?path={self._get_key(name)}'
