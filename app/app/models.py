import uuid
from typing import Optional, List

from django import forms
from django.apps import apps
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
            ('access_appstream', 'Can access appstream'),
        ]

    def __str__(self):
        return f'{self.owner} / {self.public_host} / {self.state}'


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

    def __str__(self):
        return f'{self.grouping.name} - {self.name}'

    def user_has_access(self, user):
        return self.user_access_type == 'REQUIRES_AUTHENTICATION' or \
            self.datasetuserpermission_set.filter(user=user).exists()


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

    def __str__(self):
        return self.name


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

    class Meta:
        verbose_name = 'Reference Data Set'

    def __str__(self):
        return '{}: {}'.format(
            self.group.name,
            self.name
        )

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.schema_version += 1
        create = self.pk is None
        super().save(force_insert, force_update, using, update_fields)
        if create:
            with connection.schema_editor() as editor:
                editor.create_model(self.get_record_model_class())

    @property
    def table_name(self):
        return 'refdata__{}'.format(self.id)

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

    def get_record_model_class(self) -> object:
        """
        Dynamically build a model class to represent a record in a dataset.
        If the class has been registered previously remove it from the cache before recreating.
        :return: dynamic model class
        """
        try:
            model = apps.all_models['app'][self.table_name]
        except KeyError:
            pass
        else:
            if model.__schema_version__ == self.schema_version:
                return model

        try:
            del apps.all_models['app'][self.table_name]
        except KeyError:
            pass

        class Meta:
            app_label = 'app'
            db_table = self.table_name
            ordering = ('updated_date',)

        attrs = {
            **{f.column_name: f.get_model_field() for f in self.fields.all()},
            '__module__': 'app',
            '__schema_version__': self.schema_version,
            'Meta': Meta,
            'reference_dataset': models.ForeignKey(
                'app.ReferenceDataset',
                on_delete=models.CASCADE
            ),
            'updated_date': models.DateTimeField(auto_now=True),
        }

        # During the above DB queries, another request may have created and
        # registered the model. Ensure we don't attempt to register another one
        # since Django will raise an exception
        try:
            return apps.all_models['app'][self.table_name]
        except KeyError:
            pass

        # Registers the model in apps.all_models['app'][self.table_name]
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

    def save_record(self, internal_id: Optional[int], form_data: dict):
        """
        Save a record to the database and associate it with this reference dataset
        :param internal_id: the django id for the model (None if doesn't exist)
        :param form_data: a dictionary containing values to be saved to the row
        :return:
        """
        if internal_id is None:
            return self.get_record_model_class().objects.create(**form_data)
        records = self.get_records().filter(id=internal_id)
        records.update(**form_data)
        return records.first()

    def delete_record(self, internal_id: int):
        """
        Delete a record from the reference dataset table
        :param internal_id: the django id for the record
        :return:
        """
        self.get_record_by_internal_id(internal_id).delete()


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
        # Stash the current data type so it can be compared on save
        self._original_data_type = self.data_type

    def __str__(self):
        return '{} field: {}'.format(
            self.reference_dataset.name,
            self.name
        )

    @property
    def column_name(self):
        return 'field_{}'.format(self.id)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """
        On ReferenceDatasetField save update the associated table.
        :param force_insert:
        :param force_update:
        :param using:
        :param update_fields:
        :return:
        """
        created = self.id is None
        super().save(force_insert, force_update, using, update_fields)
        # Force increment of reference dataset schema version
        self.reference_dataset.save()
        if created:
            model_class = self.reference_dataset.get_record_model_class()
            with connection.schema_editor() as editor:
                editor.add_field(
                    model_class,
                    model_class._meta.get_field(self.column_name),
                )
        elif self._original_data_type != self.data_type:
            with connection.cursor() as cursor:
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

    def delete(self, using=None, keep_parents=False):
        model_class = self.reference_dataset.get_record_model_class()
        with connection.schema_editor() as editor:
            editor.remove_field(
                model_class,
                model_class._meta.get_field(self.column_name),
            )
        super().delete(using, keep_parents)

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
