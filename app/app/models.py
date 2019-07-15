import re
import uuid
from typing import Optional, List, Type

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models, connection
from django.db.models.signals import post_save
from django.dispatch import receiver
from psycopg2 import sql

from app.common.models import TimeStampedModel, DeletableTimestampedUserModel, TimeStampedUserModel


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sso_id = models.UUIDField(unique=True, default=uuid.uuid4)


@receiver(post_save, sender=User)
def save_user_profile(instance, **_):
    try:
        profile = instance.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=instance)
    profile.save()


class Database(TimeStampedModel):
    # Deliberately no indexes: current plan is only a few public databases.

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    memorable_name = models.CharField(
        validators=[RegexValidator(regex=r'[A-Za-z0-9_]')],
        max_length=128,
        blank=False,
        unique=True,
        help_text='Must match the set of environment variables starting with DATA_DB__[memorable_name]__',
    )
    is_public = models.BooleanField(
        default=False,
        help_text='If public, the same credentials for the database will be shared with each user. If not public, each user must be explicilty given access, and temporary credentials will be created for each.'
    )

    def __str__(self):
        return f'{self.memorable_name}'


class ApplicationTemplate(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        validators=[RegexValidator(regex=r'^[a-z]+$')],
        max_length=128,
        blank=False,
        help_text='Used in URLs: only lowercase letters allowed',
        unique=True,
    )
    nice_name = models.CharField(
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\- ]+$')],
        max_length=128,
        blank=False,
        unique=True,
    )
    spawner = models.CharField(
        max_length=10,
        choices=(
            ('PROCESS', 'Process'),
        ),
        default='PROCESS',
    )
    spawner_options = models.CharField(
        max_length=10240,
        help_text='Options that the spawner understands to start the application',
    )

    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f'{self.name}'


class ApplicationInstance(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(User, on_delete=models.PROTECT)

    # Stored explicitly to allow matching if URL scheme changed
    public_host = models.CharField(
        max_length=63,
        help_text='The leftmost part of the domain name of this application',
    )

    # Copy of the options to allow for spawners to be changed after (or during) spawning
    application_template = models.ForeignKey(ApplicationTemplate, on_delete=models.PROTECT)
    spawner = models.CharField(
        max_length=15,
        help_text='The spawner used to start the application',
    )
    spawner_application_template_options = models.CharField(
        max_length=10240,
        help_text='The spawner options at the time the application instance was spawned',
    )

    spawner_application_instance_id = models.CharField(
        max_length=128,
        help_text='An ID that the spawner understands to control and report on the application',
    )

    state = models.CharField(
        max_length=16,
        choices=(
            ('SPAWNING', 'Spawning'),
            ('RUNNING', 'Running'),
            ('STOPPED', 'Stopped'),
        ),
        default='SPAWNING',
    )
    proxy_url = models.CharField(
        max_length=256,
        help_text='The URL that the proxy can proxy HTTP and WebSockets requests to',
    )

    # The purpose of this field is to raise an IntegrityError if multiple running or spawning
    # instances for the same public host name are created, but to allow multiple stopped or
    # errored
    single_running_or_spawning_integrity = models.CharField(
        max_length=63,
        unique=True,
        help_text='Used internally to avoid duplicate running applications'
    )

    class Meta:
        indexes = [
            models.Index(fields=['owner', 'created_date']),
            models.Index(fields=['public_host', 'state']),
        ]
        permissions = [
            ('start_all_applications', 'Can start all applications'),
        ]

    def __str__(self):
        return f'{self.owner} / {self.public_host} / {self.state}'


class DataGrouping(TimeStampedModel):
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

    def __str__(self):
        return f'{self.grouping.name} - {self.name}'


class DataSetUserPermission(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )

    class Meta:
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


class SourceLink(TimeStampedModel):
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
        blank=False,
        null=False,
        max_length=128,
        help_text='Used as the displayed text in the download link',
    )
    url = models.CharField(
        max_length=256,
    )

    format = models.CharField(blank=False, null=False, max_length=10)
    frequency = models.CharField(blank=False, null=False, max_length=50)


class ReferenceDataset(DeletableTimestampedUserModel):
    group = models.ForeignKey(
        DataGrouping,
        on_delete=models.CASCADE
    )
    name = models.CharField(
        max_length=255,
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
        null=True,
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

    class Meta:
        verbose_name = 'Reference Data Set'

    def __str__(self):
        return '{}: {}'.format(
            self.group.name,
            self.name
        )

    @property
    def table_name(self):
        return 'refdata__{}'.format(self.id)

    @property
    def field_names(self) -> List[str]:
        """
        Returns the column name for all associated fields.
        :return: list of field names
        """
        return [x.name for x in self.fields.all()]

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
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT MAX(updated_date) FROM {}'.format(
                    self.table_name
                )
            )
            record = cursor.fetchone()
            if record is not None:
                return record[0]
            return None

    def get_records(self) -> List[dict]:
        """
        Return a list of associated records containing the internal id and row data
        :return:
        """
        records = []
        if self.field_names:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        '''
                        SELECT dw_int_id, {field_names}
                        FROM {table_name}
                        ORDER BY {column_name}
                        '''
                    ).format(
                        field_names=sql.SQL(', ').join(map(sql.Identifier, self.field_names)),
                        table_name=sql.Identifier(self.table_name),
                        column_name=sql.Identifier(self.identifier_field.name)

                    )
                )
                for row in cursor.fetchall():
                    records.append({
                        'id': row[0],
                        'data': row[1:]
                    })
        return records

    def get_record_by_internal_id(self, internal_id: int) -> Optional[dict]:
        """
        Return a record using django's internal id
        :param internal_id:
        :return:
        """
        return self._get_record('dw_int_id', internal_id)

    def get_record_by_custom_id(self, record_id: any) -> Optional[dict]:
        """
        Return the record matching the custom identifier provided.
        :param record_id:
        :return:
        """
        return self._get_record(self.identifier_field.name, record_id)

    def _get_record(self, field_name: str, identifier: any) -> Optional[dict]:
        """
        Return the record with `field_name`=`identifier` for this reference dataset
        :param field_name: the identifier column name for the field
        :param identifier: the identifier value
        :return:
        """
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    '''
                    SELECT dw_int_id, {field_names}
                    FROM {table_name}
                    WHERE {column_name}=%s
                    '''
                ).format(
                    field_names=sql.SQL(', ').join(map(sql.Identifier, self.field_names)),
                    table_name=sql.Identifier(self.table_name),
                    column_name=sql.Identifier(self.identifier_field.name)
                ), [
                    identifier
                ]
            )
            row = cursor.fetchone()
            if row is not None:
                record = {}
                for idx, name in enumerate([x.name for x in cursor.description]):
                    record[name] = row[idx]
                return record
            return None

    def save_record(self, internal_id: Optional[int], form_data: dict):
        """
        Save a record to the database and associate it with this reference dataset
        :param internal_id: the django id for the model (None if doesn't exist)
        :param form_data: a dictionary containing values to be saved to the row
        :return:
        """
        with connection.cursor() as cursor:
            if internal_id is None:
                cursor.execute(
                    sql.SQL(
                        '''
                        INSERT INTO {table_name} (reference_dataset_id, {columns}) 
                        VALUES (%s, {values})
                        '''
                    ).format(
                        table_name=sql.Identifier(self.table_name),
                        columns=sql.SQL(', ').join(map(sql.Identifier, form_data.keys())),
                        values=sql.SQL(', ').join(sql.Placeholder() * len(form_data)),
                    ),
                    [self.id] + list(form_data.values())
                )
            else:
                cursor.execute(
                    sql.SQL(
                        '''
                        UPDATE {table_name}
                        SET {params}
                        WHERE dw_int_id=%s
                        '''
                    ).format(
                        table_name=sql.Identifier(self.table_name),
                        params=sql.SQL(', ').join([
                            sql.SQL('{}={}').format(
                                sql.Identifier(k), sql.Placeholder()
                            ) for k in form_data.keys()
                        ])
                    ),
                    list(form_data.values()) + [internal_id]
                )

    def delete_record(self, internal_id: int):
        """
        Delete a record from the reference dataset table
        :param internal_id: the django id for the record
        :return:
        """
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    '''
                    DELETE FROM {}
                    WHERE dw_int_id=%s
                    '''
                ).format(
                    sql.Identifier(self.table_name)
                ), [
                    internal_id
                ]
            )


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
    _DATA_TYPE_FIELD_MAP = {
        DATA_TYPE_CHAR: forms.CharField,
        DATA_TYPE_INT: forms.IntegerField,
        DATA_TYPE_FLOAT: forms.FloatField,
        DATA_TYPE_DATE: forms.DateField,
        DATA_TYPE_TIME: forms.TimeField,
        DATA_TYPE_DATETIME: forms.DateTimeField,
        DATA_TYPE_BOOLEAN: forms.BooleanField,
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
        max_length=60,
        help_text='The name of the field. May only contain letters '
                  'numbers and underscores (no spaces)',
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')]
    )
    description = models.TextField(
        blank=True,
        null=True
    )
    required = models.BooleanField(default=False)

    class Meta:
        unique_together = ('reference_dataset', 'name')
        verbose_name = 'Reference Data Set Field'
        ordering = ('id',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Save the models current values so they can be compared
        # in the post save signal handler
        self._original_values = {
            'name': self.name,
            'required': self.required,
            'data_type': self.data_type,
        }

    def __str__(self):
        return '{} field: {}'.format(
            self.reference_dataset.name,
            self.name
        )

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
        field = self._DATA_TYPE_FIELD_MAP.get(self.data_type, forms.CharField)()
        if self.data_type == self.DATA_TYPE_DATE:
            field.widget = forms.DateInput(attrs={'type': 'date'})
        elif self.data_type == self.DATA_TYPE_TIME:
            field.widget = forms.DateInput(attrs={'type': 'time'})
        field.required = self.is_identifier or self.required
        field.widget.attrs['required'] = field.required
        return field
