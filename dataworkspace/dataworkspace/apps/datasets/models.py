import copy
import uuid

from typing import Optional, List

from psycopg2 import sql

import boto3
from botocore.exceptions import ClientError
from ckeditor.fields import RichTextField

from django import forms
from django.apps import apps
from django.db import models, connection, connections, transaction, ProgrammingError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError, Count, Q
from django.contrib.postgres.fields import JSONField, ArrayField
from django.utils.text import slugify
from django.utils import timezone

from dataworkspace.apps.core.models import (
    TimeStampedModel,
    DeletableTimestampedUserModel,
    TimeStampedUserModel,
    Database,
    DeletableQuerySet,
)
from dataworkspace.apps.datasets.model_utils import (
    external_model_class,
    has_circular_link,
    get_linked_field_display_name,
    get_linked_field_identifier_name,
)


class DataGroupingManager(DeletableQuerySet):
    def with_published_datasets(self):
        """
        Returns only datasets that contain one or more published
        datasets or reference datasets
        """
        return (
            self.live()
            .annotate(
                num_published_datasets=Count(
                    'dataset', filter=Q(dataset__published=True)
                ),
                num_published_reference_datasets=Count(
                    'referencedataset', filter=Q(referencedataset__published=True)
                ),
            )
            .filter(
                Q(num_published_datasets__gt=0)
                | Q(num_published_reference_datasets__gt=0)
            )
        )


class DataGrouping(DeletableTimestampedUserModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # 128 - small tweet in length
    name = models.CharField(unique=True, blank=False, null=False, max_length=128)
    # 256 i.e. a long tweet length
    short_description = models.CharField(blank=False, null=False, max_length=256)
    description = models.TextField(blank=True, null=True)

    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_owner',
        null=True,
        blank=True,
    )

    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_manager',
        null=True,
        blank=True,
    )

    slug = models.SlugField(
        max_length=50, db_index=True, unique=True, null=False, blank=False
    )

    objects = DataGroupingManager()

    class Meta:
        db_table = 'app_datagrouping'

    def __str__(self):
        return f'{self.name}'


class SourceTag(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class DataSet(TimeStampedModel):
    TYPE_MASTER_DATASET = 1
    TYPE_DATA_CUT = 2
    _DATASET_TYPE_CHOICES = (
        (TYPE_MASTER_DATASET, 'Master Dataset'),
        (TYPE_DATA_CUT, 'Data Cut'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.IntegerField(choices=_DATASET_TYPE_CHOICES, default=TYPE_DATA_CUT)
    name = models.CharField(blank=False, null=False, max_length=128)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)
    short_description = models.CharField(blank=False, null=False, max_length=256)
    grouping = models.ForeignKey(DataGrouping, on_delete=models.CASCADE)
    description = models.TextField(null=False, blank=False)
    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    licence = models.CharField(null=True, blank=True, max_length=256)
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
    eligibility_criteria = ArrayField(models.CharField(max_length=256), null=True)
    number_of_downloads = models.PositiveIntegerField(default=0)
    source_tags = models.ManyToManyField(SourceTag, related_name='+', blank=True)

    class Meta:
        db_table = 'app_dataset'

    def __str__(self):
        return f'{self.grouping.name} - {self.name}'

    def user_has_access(self, user):
        return (
            self.user_access_type == 'REQUIRES_AUTHENTICATION'
            or self.datasetuserpermission_set.filter(user=user).exists()
        )

    def clone(self):
        """Create a copy of the dataset and any related objects.

        New dataset is unpublished and has a name prefixed with
        "Copy of <original dataset name>".

        Related objects (excluding user permissions) are duplicated
        for the new dataset.

        """

        CLONE_RELATED_FIELDS = [
            'sourcetable',
            'sourceview',
            'sourcelink',
            'customdatasetquery',
        ]

        clone = copy.copy(self)

        clone.pk = None
        clone.name = f'Copy of {self.name}'
        clone.slug = ''
        clone.number_of_downloads = 0
        clone.published = False
        clone.save()

        for related_field in CLONE_RELATED_FIELDS:
            related_objects = [
                copy.copy(obj) for obj in getattr(self, related_field + "_set").all()
            ]
            for obj in related_objects:
                obj.pk = None
                obj.dataset = clone
                obj.save()

        return clone

    def get_admin_edit_url(self):
        if self.type == self.TYPE_MASTER_DATASET:
            return reverse('admin:datasets_masterdataset_change', args=(self.id,))
        return reverse('admin:datasets_datacutdataset_change', args=(self.id,))


class DataSetUserPermission(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)

    class Meta:
        db_table = 'app_datasetuserpermission'
        unique_together = ('user', 'dataset')


class MasterDatasetManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(type=DataSet.TYPE_MASTER_DATASET)


class MasterDataset(DataSet):
    """
    Proxy model to allow to logically separate out "master" and "data cut" datasets in the admin.
    """

    objects = MasterDatasetManager()

    class Meta:
        proxy = True
        verbose_name = 'Master Dataset'


class MasterDatasetUserPermission(DataSetUserPermission):
    """
    Proxy model to allow for separate admin pages for master and data cut datasets
    """

    class Meta:
        proxy = True


class DataCutDatasetManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(type=DataSet.TYPE_DATA_CUT)


class DataCutDataset(DataSet):
    """
    Proxy model to allow to logically separate out "master" and "data cut" datasets in the admin.
    """

    objects = DataCutDatasetManager()

    class Meta:
        proxy = True
        verbose_name = 'Data Cut Dataset'


class DataCutDatasetUserPermission(DataSetUserPermission):
    """
    Proxy model to allow for separate admin pages for master and data cut datasets
    """

    class Meta:
        proxy = True


class BaseSource(TimeStampedModel):
    FREQ_DAILY = 1
    FREQ_WEEKLY = 2
    FREQ_MONTHLY = 3
    FREQ_QUARTERLY = 4
    FREQ_ANNUALLY = 5
    _FREQ_CHOICES = (
        (FREQ_DAILY, 'Daily'),
        (FREQ_WEEKLY, 'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
        (FREQ_QUARTERLY, 'Quarterly'),
        (FREQ_ANNUALLY, 'Annually'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    name = models.CharField(
        max_length=1024,
        blank=False,
        help_text='Used as the displayed text in the download link',
    )
    database = models.ForeignKey(Database, default=None, on_delete=models.CASCADE)
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
        default='public',
    )
    frequency = models.IntegerField(choices=_FREQ_CHOICES, default=FREQ_DAILY)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class SourceTable(BaseSource):
    table = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
    )
    accessible_by_google_data_studio = models.BooleanField(
        default=False, help_text='Only Superusers can access the data'
    )

    class Meta:
        db_table = 'app_sourcetable'

    def __str__(self):
        return f'{self.name} ({self.id})'

    def get_google_data_studio_link(self):
        return settings.GOOGLE_DATA_STUDIO_CONNECTOR_PATTERN.replace(
            '<table-id>', str(self.id)
        )


class SourceView(BaseSource):
    view = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
    )

    def get_absolute_url(self):
        return reverse(
            'catalogue:dataset_source_view_download',
            args=(self.dataset.grouping.slug, self.dataset.slug, self.id),
        )


class SourceLink(TimeStampedModel):
    TYPE_EXTERNAL = 1
    TYPE_LOCAL = 2
    _LINK_TYPES = ((TYPE_EXTERNAL, 'External Link'), (TYPE_LOCAL, 'Local Link'))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    link_type = models.IntegerField(choices=_LINK_TYPES, default=TYPE_EXTERNAL)
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
            client.head_object(Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url)
        except ClientError:
            return False
        return True

    def _delete_s3_file(self):
        if self.local_file_is_accessible():
            client = boto3.client('s3')
            client.delete_object(Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
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
            args=(self.dataset.grouping.slug, self.dataset.slug, self.id),
        )


class CustomDatasetQuery(TimeStampedModel):
    FREQ_DAILY = 1
    FREQ_WEEKLY = 2
    FREQ_MONTHLY = 3
    FREQ_QUARTERLY = 4
    FREQ_ANNUALLY = 5
    _FREQ_CHOICES = (
        (FREQ_DAILY, 'Daily'),
        (FREQ_WEEKLY, 'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
        (FREQ_QUARTERLY, 'Quarterly'),
        (FREQ_ANNUALLY, 'Annually'),
    )
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    query = models.TextField()
    frequency = models.IntegerField(choices=_FREQ_CHOICES)

    class Meta:
        verbose_name = 'SQL Query'
        verbose_name_plural = 'SQL Queries'

    def get_absolute_url(self):
        return reverse(
            'catalogue:dataset_query_download',
            args=(self.dataset.grouping.slug, self.dataset.slug, self.id),
        )

    def get_filename(self):
        return '{}.csv'.format(slugify(self.name))


class ReferenceDataset(DeletableTimestampedUserModel):
    SORT_DIR_ASC = 1
    SORT_DIR_DESC = 2
    _SORT_DIR_CHOICES = ((SORT_DIR_ASC, 'Ascending'), (SORT_DIR_DESC, 'Descending'))
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    is_joint_dataset = models.BooleanField(default=False)
    group = models.ForeignKey(DataGrouping, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
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
                'lowercase letters, numbers and underscores',
            )
        ],
    )
    slug = models.SlugField()
    short_description = models.CharField(max_length=255)
    description = RichTextField(null=True, blank=True)
    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    licence = models.CharField(null=False, blank=True, max_length=256)
    restrictions_on_usage = models.TextField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    published = models.BooleanField(default=False)

    initial_published_at = models.DateField(null=True, blank=True)
    published_at = models.DateField(null=True, blank=True)

    schema_version = models.IntegerField(default=0)

    major_version = models.IntegerField(default=1)
    minor_version = models.IntegerField(default=0)

    published_major_version = models.IntegerField(default=0)
    published_minor_version = models.IntegerField(default=0)

    external_database = models.ForeignKey(
        Database,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text='Name of the analysts database to keep in '
        'sync with this reference dataset',
    )
    sort_field = models.ForeignKey(
        'ReferenceDatasetField',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='The field to order records by in any outputs. '
        'If not set records will be sorted by last updated date.',
    )
    sort_direction = models.IntegerField(
        default=SORT_DIR_ASC, choices=_SORT_DIR_CHOICES
    )
    number_of_downloads = models.PositiveIntegerField(default=0)
    source_tags = models.ManyToManyField(SourceTag, related_name='+', blank=True)

    class Meta:
        db_table = 'app_referencedataset'
        verbose_name = 'Reference dataset'

    def __str__(self):
        return '{}: {}'.format(self.group.name, self.name)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current table name & db so they can be compared on save
        self._original_table_name = self.table_name
        self._original_ext_db = self.external_database
        self._original_sort_order = self.record_sort_order
        self._original_published = self.published

    def _schema_has_changed(self):
        return (
            self.table_name != self._original_table_name
            or self.record_sort_order != self._original_sort_order
        )

    def manage_published(self, create):
        if not self.published:
            return

        if not self.initial_published_at:
            self.initial_published_at = timezone.now()
            self.major_version = 1
            self.minor_version = 0

        if self._original_published and not create:
            self.published_major_version = self.major_version
            self.published_minor_version = self.minor_version
        else:
            self.published_at = timezone.now()
            if self.major_version > self.published_major_version:
                self.published_major_version += 1
                self.published_minor_version = 0
            elif self.minor_version > self.published_minor_version:
                self.published_minor_version += 1
            self.major_version = self.published_major_version
            self.minor_version = self.published_minor_version

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        create = self.pk is None
        if not create and self._schema_has_changed():
            self.schema_version += 1

        self.manage_published(create)

        super().save(force_insert, force_update, using, update_fields)
        model_class = self.get_record_model_class()
        if create:
            # Create the internal database table
            with connection.schema_editor() as editor:
                editor.create_model(model_class)
            # Create the external database table
            if self.external_database is not None:
                self._create_external_database_table(
                    self.external_database.memorable_name
                )
        else:
            if self.external_database != self._original_ext_db:
                # If external db has been changed delete the original table
                if self._original_ext_db is not None:
                    self._drop_external_database_table(
                        self._original_ext_db.memorable_name
                    )
                # if external db is now set create the table and sync existing records
                if self.external_database is not None:
                    self._create_external_database_table(
                        self.external_database.memorable_name
                    )
                    self.sync_to_external_database(
                        self.external_database.memorable_name
                    )

            # If the db has been changed update it
            if self._schema_has_changed():
                for database in self.get_database_names():
                    with connections[database].schema_editor() as editor:
                        editor.alter_db_table(
                            model_class, self._original_table_name, self.table_name
                        )

        self._original_table_name = self.table_name
        self._original_ext_db = self.external_database
        self._original_sort_order = self.record_sort_order

    @transaction.atomic
    def delete(self, **kwargs):
        # Do not allow deletion if this dataset is referenced by other datasets
        linking_fields = ReferenceDatasetField.objects.filter(
            linked_reference_dataset=self
        )
        if linking_fields.count() > 0:
            raise ProtectedError(
                'Cannot delete reference dataset as it is linked to by other datasets',
                set(x.reference_dataset for x in linking_fields),
            )

        # Delete external table when ref dataset is deleted
        if self.external_database is not None:
            self._drop_external_database_table(self.external_database.memorable_name)
        super().delete(**kwargs)

    def _create_external_database_table(self, db_name):
        with connections[db_name].schema_editor() as editor:
            with external_model_class(self.get_record_model_class()) as mc:
                editor.create_model(mc)

    def _drop_external_database_table(self, db_name):
        with connections[db_name].schema_editor() as editor:
            try:
                editor.delete_model(self.get_record_model_class())
            except ProgrammingError:
                pass

    @property
    def field_names(self) -> List[str]:
        """
        Returns the display name for all associated fields.
        :return: list of field names
        """
        return [x.name for x in self.fields.all()]

    @property
    def editable_fields(self):
        """
        Returns related ReferenceDatasetFields that are user editable
        :return:
        """
        return self.fields.filter(
            data_type__in=ReferenceDatasetField.EDITABLE_DATA_TYPES
        )

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
    def display_name_field(self) -> 'ReferenceDatasetField':
        """
        Returns the associated `ReferenceDataField` with `is_display_name`=True.
        Falls back to the identifier field if no display name is set.
        :return:
        """
        try:
            return self.fields.get(is_display_name=True)
        except ReferenceDatasetField.DoesNotExist:
            return self.fields.get(is_identifier=True)

    @property
    def export_field_names(self) -> List[str]:
        """
        Returns the field names for download files (including id/name from linked datasets)
        :return: list of display field names
        """
        field_names = []
        for field in self.fields.all():
            if field.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                field_names.append(get_linked_field_identifier_name(field))
                field_names.append(get_linked_field_display_name(field))
            else:
                field_names.append(field.name)
        return field_names

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

    @property
    def published_version(self):
        return '{}.{}'.format(
            self.published_major_version, self.published_minor_version
        )

    @property
    def record_sort_order(self):
        """
        Return ordering tuple for reference dataset records.
        If column type is foreign key sort on display name for the related model.
        :return:
        """
        prefix = '-' if self.sort_direction == self.SORT_DIR_DESC else ''
        order = 'updated_date'
        if self.sort_field is not None:
            field = self.sort_field
            order = field.column_name
            if (
                field.data_type == field.DATA_TYPE_FOREIGN_KEY
                and field.linked_reference_dataset is not None
            ):
                order = '{}__{}'.format(
                    field.column_name,
                    field.linked_reference_dataset.display_name_field.column_name,
                )
        return [''.join([prefix, order])]

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
            ordering = self.record_sort_order

        attrs = {
            **{f.column_name: f.get_model_field() for f in self.fields.all()},
            '__module__': 'datasets',
            '__schema_version__': self.schema_version,
            'Meta': Meta,
        }

        # During the above DB queries, another request may have created and
        # registered the model. Ensure we don't attempt to register another one
        # since Django will raise an exception
        try:
            return apps.all_models['datasets'][self.table_name]
        except KeyError:
            pass

        # Registers the model in apps.all_models['datasets'][self.table_name]
        return type(self.table_name, (ReferenceDatasetRecordBase,), attrs)

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
    def save_record(
        self, internal_id: Optional[int], form_data: dict, sync_externally=True
    ):
        """
        Save a record to the local database and associate it with this reference dataset.
        Replicate the record in any linked external databases.
        :param internal_id: the django id for the model (None if doesn't exist)
        :param form_data: a dictionary containing values to be saved to the row
        :param sync_externally: Whether to run a full sync on the external db
        :return:
        """
        if internal_id is None:
            record = self.get_record_model_class().objects.create(**form_data)
        else:
            records = self.get_records().filter(id=internal_id)
            records.update(**form_data)
            record = records.first()
        self.increment_minor_version()
        if sync_externally and self.external_database is not None:
            self.sync_to_external_database(self.external_database.memorable_name)
        return record

    @transaction.atomic
    def delete_record(self, internal_id: int, sync_externally=True):
        """
        Delete a record from the reference dataset table
        :param internal_id: the django id for the record
        :param sync_externally: Whether to run a full sync on the external db
        :return:
        """
        self.increment_minor_version()
        self.get_record_by_internal_id(internal_id).delete()
        if sync_externally and self.external_database is not None:
            self.sync_to_external_database(self.external_database.memorable_name)

    def sync_to_external_database(self, external_database):
        """
        Run a full sync of records from the local django db to `external_database`
        :param external_database:
        :return:
        """
        model_class = self.get_record_model_class()
        saved_ids = []

        for record in self.get_records():
            record_data = {
                field.column_name: getattr(record, field.column_name)
                for field in self.fields.exclude(
                    data_type__in=ReferenceDatasetField.PROPERTY_DATA_TYPES
                )
            }
            if (
                model_class.objects.using(external_database)
                .filter(pk=record.id)
                .exists()
            ):
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).filter(pk=record.id).update(
                        **record_data
                    )
            else:
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).create(
                        id=record.id, **record_data
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


class ReferenceDatasetRecordBase(models.Model):
    reference_dataset = models.ForeignKey(
        ReferenceDataset, on_delete=models.CASCADE, related_name='records'
    )
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        return getattr(
            self,
            self.reference_dataset.display_name_field.column_name,
            'Unknown record',
        )

    def get_identifier(self):
        return getattr(self, self.reference_dataset.identifier_field.column_name, None)


class ReferenceDatasetField(TimeStampedUserModel):
    DATA_TYPE_CHAR = 1
    DATA_TYPE_INT = 2
    DATA_TYPE_FLOAT = 3
    DATA_TYPE_DATE = 4
    DATA_TYPE_TIME = 5
    DATA_TYPE_DATETIME = 6
    DATA_TYPE_BOOLEAN = 7
    DATA_TYPE_FOREIGN_KEY = 8
    DATA_TYPE_UUID = 9
    DATA_TYPE_AUTO_ID = 10
    _DATA_TYPES = (
        (DATA_TYPE_CHAR, 'Character field'),
        (DATA_TYPE_INT, 'Integer field'),
        (DATA_TYPE_FLOAT, 'Float field'),
        (DATA_TYPE_DATE, 'Date field'),
        (DATA_TYPE_TIME, 'Time field'),
        (DATA_TYPE_DATETIME, 'Datetime field'),
        (DATA_TYPE_BOOLEAN, 'Boolean field'),
        (DATA_TYPE_FOREIGN_KEY, 'Linked Reference Dataset'),
        (DATA_TYPE_UUID, 'Universal unique identifier field'),
        (DATA_TYPE_AUTO_ID, 'Auto incrementing integer field'),
    )
    DATA_TYPE_MAP = {
        DATA_TYPE_CHAR: 'varchar(255)',
        DATA_TYPE_INT: 'integer',
        DATA_TYPE_FLOAT: 'float',
        DATA_TYPE_DATE: 'date',
        DATA_TYPE_TIME: 'time',
        DATA_TYPE_DATETIME: 'timestamp',
        DATA_TYPE_BOOLEAN: 'boolean',
        DATA_TYPE_FOREIGN_KEY: 'integer',
        DATA_TYPE_UUID: 'uuid',
        DATA_TYPE_AUTO_ID: 'integer',
    }
    _DATA_TYPE_FORM_FIELD_MAP = {
        DATA_TYPE_CHAR: forms.CharField,
        DATA_TYPE_INT: forms.IntegerField,
        DATA_TYPE_FLOAT: forms.FloatField,
        DATA_TYPE_DATE: forms.DateField,
        DATA_TYPE_TIME: forms.TimeField,
        DATA_TYPE_DATETIME: forms.DateTimeField,
        DATA_TYPE_BOOLEAN: forms.BooleanField,
        DATA_TYPE_FOREIGN_KEY: forms.ModelChoiceField,
        DATA_TYPE_UUID: forms.UUIDField,
        DATA_TYPE_AUTO_ID: forms.IntegerField,
    }
    _DATA_TYPE_MODEL_FIELD_MAP = {
        DATA_TYPE_CHAR: models.CharField,
        DATA_TYPE_INT: models.IntegerField,
        DATA_TYPE_FLOAT: models.FloatField,
        DATA_TYPE_DATE: models.DateField,
        DATA_TYPE_TIME: models.TimeField,
        DATA_TYPE_DATETIME: models.DateTimeField,
        DATA_TYPE_BOOLEAN: models.BooleanField,
        DATA_TYPE_FOREIGN_KEY: models.ForeignKey,
        DATA_TYPE_UUID: models.UUIDField,
        DATA_TYPE_AUTO_ID: models.AutoField,
    }
    EDITABLE_DATA_TYPES = (
        DATA_TYPE_CHAR,
        DATA_TYPE_INT,
        DATA_TYPE_FLOAT,
        DATA_TYPE_DATE,
        DATA_TYPE_TIME,
        DATA_TYPE_DATETIME,
        DATA_TYPE_BOOLEAN,
        DATA_TYPE_FOREIGN_KEY,
    )
    PROPERTY_DATA_TYPES = (DATA_TYPE_AUTO_ID,)
    reference_dataset = models.ForeignKey(
        ReferenceDataset, on_delete=models.CASCADE, related_name='fields'
    )
    data_type = models.IntegerField(choices=_DATA_TYPES)
    is_identifier = models.BooleanField(
        default=False, help_text='This field is the unique identifier for the record'
    )
    is_display_name = models.BooleanField(
        default=False,
        help_text='This field is the name that will be displayed when '
        'referenced by other datasets',
    )
    name = models.CharField(max_length=255, help_text='The display name for the field')
    column_name = models.CharField(
        max_length=255,
        blank=False,
        help_text='Descriptive column name for the field - '
        'Column name will be used in external databases',
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$',
                message='Column names must start with a letter and contain only '
                'letters, numbers, underscores and full stops.',
            )
        ],
    )
    description = models.TextField(blank=True, null=True)
    required = models.BooleanField(default=False)
    linked_reference_dataset = models.ForeignKey(
        ReferenceDataset,
        on_delete=models.PROTECT,
        related_name='linked_fields',
        null=True,
        blank=True,
    )
    sort_order = models.PositiveIntegerField(default=0, blank=False, null=False)
    # legacy_reference_dataset_id = models.IntegerField(null=True)
    # legacy_linked_reference_dataset_id = models.IntegerField(null=True)

    class Meta:
        db_table = 'app_referencedatasetfield'
        unique_together = (
            ('reference_dataset', 'name'),
            ('reference_dataset', 'column_name'),
        )
        verbose_name = 'Reference dataset field'
        ordering = ('sort_order',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current data type and name so they can be compared on save
        self._original_data_type = self.data_type
        self._original_column_name = self.column_name

    def __str__(self):
        return '{} field: {}'.format(self.reference_dataset.name, self.name)

    def _add_column_to_db(self):
        """
        Add a column to the refdata table in the db
        :return:
        """
        super().save()
        self.reference_dataset.increment_schema_version()
        if self.data_type not in self.PROPERTY_DATA_TYPES:
            model_class = self.reference_dataset.get_record_model_class()
            for database in self.reference_dataset.get_database_names():
                with connections[database].schema_editor() as editor:
                    editor.add_field(
                        model_class, model_class._meta.get_field(self.column_name)
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
        if self.data_type not in self.PROPERTY_DATA_TYPES:
            # Get a copy of the updated model class (post-save)
            model_class = self.reference_dataset.get_record_model_class()
            # Get a copy of the new field
            to_field = model_class._meta.get_field(self.column_name)
            # Migrate from old field to new field
            with transaction.atomic():
                for database in self.reference_dataset.get_database_names():
                    with connections[database].schema_editor() as editor:
                        editor.alter_field(model_class, from_field, to_field)

    def _update_db_column_data_type(self):
        super().save()
        self.reference_dataset.increment_schema_version()
        if self.data_type not in self.PROPERTY_DATA_TYPES:
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
                            table_name=sql.Identifier(
                                self.reference_dataset.table_name
                            ),
                            column_name=sql.Identifier(self.column_name),
                            data_type=sql.SQL(self.get_postgres_datatype()),
                        )
                    )

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        """
        On ReferenceDatasetField save update the associated table.
        :param force_insert:
        :param force_update:
        :param using:
        :param update_fields:
        :return:
        """
        ref_dataset = self.reference_dataset

        # Disallow circular linking of reference datasets
        if self.data_type == self.DATA_TYPE_FOREIGN_KEY and has_circular_link(
            self.reference_dataset, self.linked_reference_dataset
        ):
            raise ValidationError(
                'Unable to link reference datasets back to each other'
            )

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
        if (
            ref_dataset.major_version > 1 or ref_dataset.minor_version > 0
        ) or ref_dataset.get_records().exists():
            self.reference_dataset.increment_major_version()
        super().save()

    @transaction.atomic
    def delete(self, using=None, keep_parents=False):
        if self.data_type not in self.PROPERTY_DATA_TYPES:
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
        field_data = {'label': self.name}
        if self.data_type == self.DATA_TYPE_DATE:
            field_data['widget'] = forms.DateInput(attrs={'type': 'date'})
        elif self.data_type == self.DATA_TYPE_TIME:
            field_data['widget'] = forms.DateInput(attrs={'type': 'time'})
        elif self.data_type == self.DATA_TYPE_FOREIGN_KEY:
            field_data['queryset'] = self.linked_reference_dataset.get_records()
        field_data['required'] = self.is_identifier or self.required
        field = self._DATA_TYPE_FORM_FIELD_MAP.get(self.data_type)(**field_data)
        field.widget.attrs['required'] = field.required
        return field

    def get_model_field(self):
        """
        Instantiates a django model field based on this models selected `data_type`.
        :return:
        """
        model_field = self._DATA_TYPE_MODEL_FIELD_MAP.get(self.data_type)
        model_config = {
            'verbose_name': self.name,
            'blank': not self.is_identifier and not self.required,
            'null': not self.is_identifier and not self.required,
            'max_length': 255,
        }
        if self.data_type == self.DATA_TYPE_FOREIGN_KEY:
            model_config.update(
                {
                    'verbose_name': 'Linked Reference Dataset',
                    'to': self.linked_reference_dataset.get_record_model_class(),
                    'on_delete': models.PROTECT,
                }
            )
        elif self.data_type == self.DATA_TYPE_UUID:
            model_config.update({'default': uuid.uuid4, 'editable': False})
        elif self.data_type == self.DATA_TYPE_AUTO_ID:
            return property(lambda x: x.id)
        return model_field(**model_config)


class ReferenceDatasetUploadLog(TimeStampedUserModel):
    reference_dataset = models.ForeignKey(ReferenceDataset, on_delete=models.CASCADE)

    class Meta:
        ordering = ('created_date',)

    def additions(self):
        return self.records.filter(
            status=ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED
        )

    def updates(self):
        return self.records.filter(
            status=ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_UPDATED
        )

    def errors(self):
        return self.records.filter(
            status=ReferenceDatasetUploadLogRecord.STATUS_FAILURE
        )


class ReferenceDatasetUploadLogRecord(TimeStampedModel):
    STATUS_SUCCESS_ADDED = 1
    STATUS_SUCCESS_UPDATED = 2
    STATUS_FAILURE = 3
    _STATUS_CHOICES = (
        (STATUS_SUCCESS_ADDED, 'Record added successfully'),
        (STATUS_SUCCESS_UPDATED, 'Record updated successfully'),
        (STATUS_FAILURE, 'Record upload failed'),
    )
    upload_log = models.ForeignKey(
        ReferenceDatasetUploadLog, on_delete=models.CASCADE, related_name='records'
    )
    status = models.IntegerField(choices=_STATUS_CHOICES)
    row_data = JSONField()
    errors = JSONField(null=True)

    class Meta:
        ordering = ('created_date',)

    def __str__(self):
        return '{}: {}'.format(self.created_date, self.get_status_display())
