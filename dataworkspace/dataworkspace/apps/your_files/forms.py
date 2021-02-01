import boto3
from botocore.exceptions import ClientError
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from dataworkspace.apps.core.utils import get_s3_prefix


class CreateTableForm(forms.Form):
    path = forms.CharField(required=True)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def clean_path(self):
        path = self.cleaned_data['path']
        client = boto3.client('s3')

        if not path.startswith(get_s3_prefix(str(self.user.profile.sso_id))):
            raise ValidationError('You don\'t have permission to access this file')

        if not path.endswith('.csv'):
            raise ValidationError(
                'Invalid file type. Only CSV files are currently supported'
            )

        try:
            client.head_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path)
        except ClientError:
            raise ValidationError('This file does not exist in S3')

        return path
