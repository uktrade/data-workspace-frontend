import boto3
from botocore.exceptions import ClientError
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from dataworkspace.apps.core.utils import get_s3_prefix, table_exists


class CreateTableForm(forms.Form):
    path = forms.CharField(required=True, widget=forms.HiddenInput())
    schema = forms.CharField(required=True, widget=forms.HiddenInput())
    table_name = forms.CharField(
        required=True,
        label=False,
        widget=forms.TextInput(attrs={"class": "govuk-input"}),
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z][a-zA-Z0-9_]*$',
                message='Table names can contain only letters, numbers and underscores',
                code='invalid-table-name',
            )
        ],
    )
    force_overwrite = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        if self.initial.get('force_overwrite'):
            self.fields['table_name'].widget = forms.HiddenInput()

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

    def clean(self):
        table_name = self.cleaned_data.get('table_name')
        if table_name:
            if table_exists(
                settings.EXPLORER_DEFAULT_CONNECTION,
                self.cleaned_data['schema'],
                table_name,
            ) and not self.cleaned_data.get('force_overwrite'):
                self.add_error(
                    'table_name',
                    ValidationError(
                        'This table already exists', code='duplicate-table'
                    ),
                )

        return super().clean()
