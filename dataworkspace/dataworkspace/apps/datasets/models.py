import uuid

from typing import Optional, List
from psycopg2 import sql

import boto3
from botocore.exceptions import ClientError
from django import forms
from django.apps import apps
from django.db import models, connection, connections, transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.urls import reverse

from dataworkspace.apps.core.models import (TimeStampedModel, DeletableTimestampedUserModel, TimeStampedUserModel,
                                            Database)
from dataworkspace.apps.datasets.model_utils import external_model_class


class DataGrouping(DeletableTimestampedUserModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    # 128 - small tweet in length
    name = models.CharField(unique=True, blank=False,
                            null=False, max_length=128)
    # 256 i.e. a long tweet length
    short_description = models.CharField(
        blank=False, null=False, max_length=256)
    description = models.TextField(blank=True, null=True)

    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_owner',
        null=True,
        blank=True
    )

    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_manager',
        null=True,
        blank=True
    )

    slug = models.SlugField(max_length=50, db_index=True, unique=True, null=False, blank=False)

    class Meta:
        db_table = 'app_datagrouping'

    def __str__(self):
        return f'{self.name}'


class DataSet(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
    )
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)

    short_description = models.CharField(
        blank=False, null=False, max_length=256)

    grouping = models.ForeignKey(DataGrouping, on_delete=models.CASCADE)

    description = models.TextField(null=False, blank=False)

    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    redactions = models.TextField(null=True, blank=True)
    licence = models.CharField(null=True, blank=True, max_length=256)

    volume = models.IntegerField(null=False, blank=False)

    retention_policy = models.TextField(null=True, blank=True)
    personal_data = models.CharField(null=True, blank=True, max_length=128)

    restrictions_on_usage = models.TextField(null=True, blank=True)
    user_access_type = models.CharField(
        max_length=64,
        choices=(
            ('REQUIRES_AUTHENTICATION', 'Requires authentication'),
            ('REQUIRES_AUTHORIZATION', 'Requires authorization'),
        ),
        default='REQUIRES_AUTHORIZATION',
    )
    published = models.BooleanField(default=False)

    class Meta:
        db_table = 'app_dataset'

    def __str__(self):
        return f'{self.grouping.name} - {self.name}'

    def user_has_access(self, user):
        return self.user_access_type == 'REQUIRES_AUTHENTICATION' or \
            self.datasetuserpermission_set.filter(user=user).exists()


class DataSetUserPermission(models.Model):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = 'app_datasetuserpermission'
        unique_together = ('user', 'dataset')


class SourceTable(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=1024,
        blank=False,
        help_text='Used as the displayed text in the download link',
    )
    database = models.ForeignKey(
        Database,
        default=None,
        on_delete=models.CASCADE,
    )
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
        default='public'
    )
    table = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
    )

    class Meta:
        db_table = 'app_sourcetable'

    def get_absolute_url(self):
        return reverse(
            'catalogue:dataset_source_table_download',
            args=(self.dataset.grouping.slug, self.dataset.slug, self.id)
        )


class SourceLink(TimeStampedModel):
    TYPE_EXTERNAL = 1
    TYPE_LOCAL = 2
    _LINK_TYPES = (
        (TYPE_EXTERNAL, 'External Link'),
        (TYPE_LOCAL, 'Local Link'),
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )
    link_type = models.IntegerField(
        choices=_LINK_TYPES,
        default=TYPE_EXTERNAL
    )
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
        help_text='Used as the displayed text in the download link',
    )
    url = models.CharField(max_length=256)
    format = models.CharField(blank=False, null=False, max_length=10)
    frequency = models.CharField(blank=False, null=False, max_length=50)

    class Meta:
        db_table = 'app_sourcelink'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current link type so it can be compared on save
        self._original_url = self.url

    def __str__(self):
        return self.name

    def local_file_is_accessible(self):
        """
        Check whether we can access the file on s3
        :return:
        """
        client = boto3.client('s3')
        try:
            client.head_object(
                Bucket=settings.AWS_UPLOADS_BUCKET,
                Key=self.url
            )
        except ClientError:
            return False
        return True

    def _delete_s3_file(self):
        client = boto3.client('s3')
        client.delete_object(
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key=self.url
        )

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # Allow users to change a url from local to external and vice versa
        is_s3_link = self.url.startswith('s3://')
        was_s3_link = self._original_url.startswith('s3://')
        if self.id is not None and self._original_url != self.url:
            self.link_type = self.TYPE_LOCAL if is_s3_link else self.TYPE_EXTERNAL
        super().save(force_insert, force_update, using, update_fields)
        # If the link is no longer an s3 link delete the file
        if was_s3_link and not is_s3_link:
            self._delete_s3_file()

    def delete(self, using=None, keep_parents=False):
        if self.link_type == self.TYPE_LOCAL:
            self._delete_s3_file()
        super().delete(using, keep_parents)

    def get_absolute_url(self):
        return reverse(
            'catalogue:dataset_source_link_download',
            args=(self.dataset.grouping.slug, self.dataset.slug, self.id)
        )


class ReferenceDataset(DeletableTimestampedUserModel):
    group = models.ForeignKey(
        DataGrouping,
        on_delete=models.CASCADE
    )
    name = models.CharField(
        max_length=255,
    )
    table_name = models.CharField(
        verbose_name='Table name',
        max_length=255,
        unique=True,
        help_text='Descriptive table name for the field - Note: Must start with '
                  '"ref_" and contain only lowercase letters, numbers and underscores',
        validators=[
            RegexValidator(
                regex=r'^ref_[a-z0-9_]*$',
                message='Table names must be prefixed with "ref_" and can contain only '
                        'lowercase letters, numbers and underscores'
            ),
        ],
    )
    slug = models.SlugField()
    short_description = models.CharField(
        max_length=255
    )
    description = models.TextField(
        null=True,
        blank=True
    )
    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    licence = models.CharField(
        null=False,
        blank=True,
        max_length=256
    )
    restrictions_on_usage = models.TextField(
        null=True,
        blank=True
    )
    valid_from = models.DateField(
        null=True,
        blank=True
    )
    valid_to = models.DateField(
        null=True,
        blank=True
    )
    published = models.BooleanField(default=False)
    schema_version = models.IntegerField(default=0)
    major_version = models.IntegerField(default=1)
    minor_version = models.IntegerField(default=0)
    external_database = models.ForeignKey(
        Database,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text='Name of the analysts database to keep in '
                  'sync with this reference dataset'
    )

    class Meta:
        db_table = 'app_referencedataset'
        verbose_name = 'Reference dataset'

    def __str__(self):
        return '{}: {}'.format(
            self.group.name,
            self.name
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current table name & db so they can be compared on save
        self._original_table_name = self.table_name
        self._original_ext_db = self.external_database \
            if self.external_database is not None else None

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        create = self.pk is None
        table_changed = self.table_name != self._original_table_name
        if not create and table_changed:
            self.schema_version += 1
        super().save(force_insert, force_update, using, update_fields)
        model_class = self.get_record_model_class()
        if create:
            # Create the internal database table
            with connection.schema_editor() as editor:
                editor.create_model(model_class)
            # Create the external database table
            if self.external_database is not None:
                self._create_external_database(self.external_database.memorable_name)
        else:
            if self.external_database != self._original_ext_db:
                # If external db has been changed delete the original table
                if self._original_ext_db is not None:
                    self._drop_external_database(self._original_ext_db.memorable_name)
                # if external db is now set create the table and sync existing records
                if self.external_database is not None:
                    self._create_external_database(self.external_database.memorable_name)
                    self.sync_to_external_database(self.external_database.memorable_name)

            # If the db has been changed update it
            if table_changed:
                for database in self.get_database_names():
                    with connections[database].schema_editor() as editor:
                        editor.alter_db_table(
                            model_class,
                            self._original_table_name,
                            self.table_name
                        )

        self._original_table_name = self.table_name
        self._original_ext_db = self.external_database \
            if self.external_database is not None else None

    @transaction.atomic
    def delete(self, **kwargs):
        # Delete external table when ref dataset is deleted
        if self.external_database is not None:
            self._drop_external_database(self.external_database.memorable_name)
        super().delete(**kwargs)

    def _create_external_database(self, db_name):
        with connections[db_name].schema_editor() as editor:
            with external_model_class(self.get_record_model_class()) as mc:
                editor.create_model(mc)

    def _drop_external_database(self, db_name):
        with connections[db_name].schema_editor() as editor:
            editor.delete_model(self.get_record_model_class())

    @property
    def field_names(self) -> List[str]:
        """
        Returns the display name for all associated fields.
        :return: list of field names
        """
        return [x.name for x in self.fields.all()]

    @property
    def column_names(self) -> List[str]:
        """
        Returns the column name for all associated fields.
        :return: list of field names
        """
        return [x.column_name for x in self.fields.all()]

    @property
    def identifier_field(self) -> 'ReferenceDatasetField':
        """
        Returns the associated `ReferenceDataField` with `is_identifier`=True
        :return:
        """
        return self.fields.get(is_identifier=True)

    @property
    def data_last_updated(self):
        """
        Return the most recent date a record was updated in the dataset
        :return:
        """
        records = self.get_records()
        if records.exists():
            return records.latest('updated_date').updated_date
        return None

    @property
    def version(self):
        return '{}.{}'.format(self.major_version, self.minor_version)

    def get_record_model_class(self) -> object:
        """
        Dynamically build a model class to represent a record in a dataset.
        If the class has been registered previously remove it from the cache before recreating.
        :return: dynamic model class
        """
        try:
            model = apps.all_models['datasets'][self.table_name]
        except KeyError:
            pass
        else:
            if model.__schema_version__ == self.schema_version:
                return model

        try:
            del apps.all_models['datasets'][self.table_name]
        except KeyError:
            pass

        class Meta:
            app_label = 'datasets'
            db_table = self.table_name
            ordering = ('updated_date',)

        attrs = {
            **{f.column_name: f.get_model_field() for f in self.fields.all()},
            '__module__': 'datasets',
            '__schema_version__': self.schema_version,
            'Meta': Meta,
            'reference_dataset': models.ForeignKey(
                'datasets.ReferenceDataset',
                on_delete=models.CASCADE
            ),
            'updated_date': models.DateTimeField(auto_now=True),
        }

        # During the above DB queries, another request may have created and
        # registered the model. Ensure we don't attempt to register another one
        # since Django will raise an exception
        try:
            return apps.all_models['datasets'][self.table_name]
        except KeyError:
            pass

        # Registers the model in apps.all_models['datasets'][self.table_name]
        return type(self.table_name, (models.Model,), attrs)

    def get_records(self) -> List[dict]:
        """
        Return a list of associated records containing the internal id and row data
        :return:
        """
        return self.get_record_model_class().objects.filter(reference_dataset=self)

    def get_record_by_internal_id(self, internal_id: int) -> Optional[dict]:
        """
        Return a record using django's internal id
        :param internal_id:
        :return:
        """
        return self._get_record('id', internal_id)

    def get_record_by_custom_id(self, record_id: any) -> Optional[dict]:
        """
        Return the record matching the custom identifier provided.
        :param record_id:
        :return:
        """
        return self._get_record(self.identifier_field.column_name, record_id)

    def _get_record(self, field_name: str, identifier: any) -> Optional[dict]:
        """
        Return the record with `field_name`=`identifier` for this reference dataset
        :param field_name: the identifier column name for the field
        :param identifier: the identifier value
        :return:
        """
        return self.get_records().get(**{field_name: identifier})

    @transaction.atomic
    def save_record(self, internal_id: Optional[int], form_data: dict):
        """
        Save a record to the local database and associate it with this reference dataset.
        Replicate the record in any linked external databases.
        :param internal_id: the django id for the model (None if doesn't exist)
        :param form_data: a dictionary containing values to be saved to the row
        :return:
        """
        cleaned_form_data = {k: v for k, v in form_data.items() if k != 'reference_data'}
        if internal_id is None:
            record = self.get_record_model_class().objects.create(**form_data)
            if self.external_database is not None:
                with external_model_class(self.get_record_model_class()) as model_class:
                    model_class.objects.using(self.external_database.memorable_name).create(
                        **cleaned_form_data
                    )
        else:
            records = self.get_records().filter(id=internal_id)
            records.update(**form_data)
            if self.external_database is not None:
                with external_model_class(self.get_record_model_class()) as model_class:
                    model_class.objects.using(self.external_database.memorable_name).filter(
                        id=internal_id
                    ).update(
                        **cleaned_form_data
                    )
            record = records.first()
        self.increment_minor_version()
        return record

    @transaction.atomic
    def delete_record(self, internal_id: int):
        """
        Delete a record from the reference dataset table
        :param internal_id: the django id for the record
        :return:
        """
        self.increment_minor_version()
        self.get_record_by_internal_id(internal_id).delete()
        if self.external_database is not None:
            with external_model_class(self.get_record_model_class()) as model_class:
                model_class.objects.using(self.external_database.memorable_name).filter(
                    id=internal_id
                ).delete()

    def sync_to_external_database(self, external_database):
        """
        Run a full sync of records from the local django db to `external_database`
        :param external_database:
        :return:
        """
        model_class = self.get_record_model_class()
        saved_ids = []

        for record in self.get_records():
            record_data = {col: getattr(record, col) for col in self.column_names}
            if model_class.objects.using(external_database).filter(pk=record.id).exists():
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).filter(pk=record.id).update(
                        **record_data
                    )
            else:
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).create(
                        id=record.id,
                        **record_data
                    )
            saved_ids.append(record.id)

        # Delete any records that are in the external db but not local
        model_class.objects.using(external_database).exclude(pk__in=saved_ids).delete()

    def increment_schema_version(self):
        self.schema_version += 1
        self.save()

    def increment_major_version(self):
        self.major_version += 1
        self.minor_version = 0
        self.save()

    def increment_minor_version(self):
        self.minor_version += 1
        self.save()

    def get_database_names(self):
        if self.external_database is not None:
            return ['default', self.external_database.memorable_name]
        return ['default']


class ReferenceDatasetField(TimeStampedUserModel):
    DATA_TYPE_CHAR = 1
    DATA_TYPE_INT = 2
    DATA_TYPE_FLOAT = 3
    DATA_TYPE_DATE = 4
    DATA_TYPE_TIME = 5
    DATA_TYPE_DATETIME = 6
    DATA_TYPE_BOOLEAN = 7
    _DATA_TYPES = (
        (DATA_TYPE_CHAR, 'Character field'),
        (DATA_TYPE_INT, 'Integer field'),
        (DATA_TYPE_FLOAT, 'Float field'),
        (DATA_TYPE_DATE, 'Date field'),
        (DATA_TYPE_TIME, 'Time field'),
        (DATA_TYPE_DATETIME, 'Datetime field'),
        (DATA_TYPE_BOOLEAN, 'Boolean field'),
    )
    DATA_TYPE_MAP = {
        DATA_TYPE_CHAR: 'varchar(255)',
        DATA_TYPE_INT: 'integer',
        DATA_TYPE_FLOAT: 'float',
        DATA_TYPE_DATE: 'date',
        DATA_TYPE_TIME: 'time',
        DATA_TYPE_DATETIME: 'timestamp',
        DATA_TYPE_BOOLEAN: 'boolean',
    }
    _DATA_TYPE_FORM_FIELD_MAP = {
        DATA_TYPE_CHAR: forms.CharField,
        DATA_TYPE_INT: forms.IntegerField,
        DATA_TYPE_FLOAT: forms.FloatField,
        DATA_TYPE_DATE: forms.DateField,
        DATA_TYPE_TIME: forms.TimeField,
        DATA_TYPE_DATETIME: forms.DateTimeField,
        DATA_TYPE_BOOLEAN: forms.BooleanField,
    }
    _DATA_TYPE_MODEL_FIELD_MAP = {
        DATA_TYPE_CHAR: models.CharField,
        DATA_TYPE_INT: models.IntegerField,
        DATA_TYPE_FLOAT: models.FloatField,
        DATA_TYPE_DATE: models.DateField,
        DATA_TYPE_TIME: models.TimeField,
        DATA_TYPE_DATETIME: models.DateTimeField,
        DATA_TYPE_BOOLEAN: models.BooleanField,
    }
    reference_dataset = models.ForeignKey(
        ReferenceDataset,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    data_type = models.IntegerField(
        choices=_DATA_TYPES
    )
    is_identifier = models.BooleanField(
        default=False,
        help_text='This field is the unique identifier for the record'
    )
    name = models.CharField(
        max_length=255,
        help_text='The display name for the field',
    )
    column_name = models.CharField(
        max_length=255,
        blank=False,
        help_text='Descriptive column name for the field - '
                  'Column name will be used in external databases',
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$',
                message='Column names must start with a letter and contain only '
                        'letters, numbers, underscores and full stops.'
            ),
        ],
    )
    description = models.TextField(
        blank=True,
        null=True
    )
    required = models.BooleanField(default=False)

    class Meta:
        db_table = 'app_referencedatasetfield'
        unique_together = (
            ('reference_dataset', 'name'),
            ('reference_dataset', 'column_name'),
        )
        verbose_name = 'Reference dataset field'
        ordering = ('id',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current data type and name so they can be compared on save
        self._original_data_type = self.data_type
        self._original_column_name = self.column_name

    def __str__(self):
        return '{} field: {}'.format(
            self.reference_dataset.name,
            self.name
        )

    def _add_column_to_db(self):
        """
        Add a column to the refdata table in the db
        :return:
        """
        super().save()
        self.reference_dataset.increment_schema_version()
        model_class = self.reference_dataset.get_record_model_class()
        for database in self.reference_dataset.get_database_names():
            with connections[database].schema_editor() as editor:
                editor.add_field(
                    model_class,
                    model_class._meta.get_field(self.column_name),
                )

    def _update_db_column_name(self):
        """
        Alter the db column name in the associated table
        :return:
        """
        # Get a copy of the existing model class (pre-save)
        model_class = self.reference_dataset.get_record_model_class()
        # Get a copy of the current field
        from_field = model_class._meta.get_field(self._original_column_name)
        # Save the changes to the field
        super().save()
        # Increment the schema version
        self.reference_dataset.increment_schema_version()
        # Get a copy of the updated model class (post-save)
        model_class = self.reference_dataset.get_record_model_class()
        # Get a copy of the new field
        to_field = model_class._meta.get_field(self.column_name)
        # Migrate from old field to new field
        with transaction.atomic():
            for database in self.reference_dataset.get_database_names():
                with connections[database].schema_editor() as editor:
                    editor.alter_field(
                        model_class,
                        from_field,
                        to_field
                    )

    def _update_db_column_data_type(self):
        super().save()
        self.reference_dataset.increment_schema_version()
        for database in self.reference_dataset.get_database_names():
            with connections[database].cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        '''
                        ALTER TABLE {table_name}
                        ALTER COLUMN {column_name} TYPE {data_type}
                        USING {column_name}::text::{data_type}
                        '''
                    ).format(
                        table_name=sql.Identifier(self.reference_dataset.table_name),
                        column_name=sql.Identifier(self.column_name),
                        data_type=sql.SQL(self.get_postgres_datatype()),
                    )
                )

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """
        On ReferenceDatasetField save update the associated table.
        :param force_insert:
        :param force_update:
        :param using:
        :param update_fields:
        :return:
        """
        ref_dataset = self.reference_dataset
        # If this is a newly created field add it to the db
        if self.id is None:
            self._add_column_to_db()
        else:
            # Otherwise update where necessary
            if self._original_column_name != self.column_name:
                self._update_db_column_name()
            if self._original_data_type != self.data_type:
                self._update_db_column_data_type()

        # Increment reference dataset major version if this is not the first save
        if (ref_dataset.major_version > 1 or ref_dataset.minor_version > 0) or \
                ref_dataset.get_records().exists():
            self.reference_dataset.increment_major_version()
        super().save()

    @transaction.atomic
    def delete(self, using=None, keep_parents=False):
        model_class = self.reference_dataset.get_record_model_class()
        for database in self.reference_dataset.get_database_names():
            with connections[database].schema_editor() as editor:
                editor.remove_field(
                    model_class,
                    model_class._meta.get_field(self._original_column_name),
                )
        super().delete(using, keep_parents)
        self.reference_dataset.increment_schema_version()
        self.reference_dataset.increment_major_version()

    def get_postgres_datatype(self) -> str:
        """
        Maps ReferenceDatasetField with Postgres' data types
        :return:
        """
        return self.DATA_TYPE_MAP.get(self.data_type)

    def get_form_field(self):
        """
        Instantiates a form field based on this models selected `data_type`.
        Falls back to `CharField` if not found.
        :return:
        """
        field = self._DATA_TYPE_FORM_FIELD_MAP.get(self.data_type)(
            label=self.name,
        )
        if self.data_type == self.DATA_TYPE_DATE:
            field.widget = forms.DateInput(attrs={'type': 'date'})
        elif self.data_type == self.DATA_TYPE_TIME:
            field.widget = forms.DateInput(attrs={'type': 'time'})
        field.required = self.is_identifier or self.required
        field.widget.attrs['required'] = field.required
        return field

    def get_model_field(self):
        """
        Instantiates a django model field based on this models selected `data_type`.
        Falls back to `CharField` if not found.
        :return:
        """
        field = self._DATA_TYPE_MODEL_FIELD_MAP.get(self.data_type)(
            verbose_name=self.name,
            blank=not self.is_identifier and not self.required,
            null=not self.is_identifier and not self.required,
            max_length=255
        )
        return field
