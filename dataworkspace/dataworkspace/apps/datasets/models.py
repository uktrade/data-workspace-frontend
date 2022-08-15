import copy
import csv
import hashlib
import json
import operator
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import reduce
from io import StringIO

from typing import Optional, List

from psycopg2 import sql

from botocore.exceptions import ClientError
from ckeditor.fields import RichTextField

from django import forms
from django.apps import apps
from django.db import (
    DatabaseError,
    models,
    connection,
    connections,
    transaction,
    ProgrammingError,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.urls import reverse
from django.db.models import F, ProtectedError, Count, Q
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.utils.text import slugify
from django.utils import timezone

from dataworkspace import datasets_db
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.models import (
    TimeStampedModel,
    DeletableTimestampedUserModel,
    TimeStampedUserModel,
    Database,
    DeletableQuerySet,
)
from dataworkspace.apps.applications.models import (
    ApplicationTemplate,
    VisualisationTemplate,
)
from dataworkspace.apps.datasets.constants import (
    DataSetType,
    DataLinkType,
    GRID_DATA_TYPE_MAP,
    GRID_ACRONYM_MAP,
    PipelineType,
    TagType,
    UserAccessType,
)
from dataworkspace.apps.datasets.model_utils import external_model_class
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.core.charts.models import ChartBuilderChart
from dataworkspace.apps.your_files.models import UploadedTable
from dataworkspace.datasets_db import (
    get_earliest_tables_last_updated_date,
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
                num_published_datasets=Count("dataset", filter=Q(dataset__published=True)),
                num_published_reference_datasets=Count(
                    "referencedataset", filter=Q(referencedataset__published=True)
                ),
            )
            .filter(Q(num_published_datasets__gt=0) | Q(num_published_reference_datasets__gt=0))
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
        related_name="asset_owner",
        null=True,
        blank=True,
    )

    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asset_manager",
        null=True,
        blank=True,
    )

    slug = models.SlugField(max_length=50, db_index=True, unique=True, null=False, blank=False)

    objects = DataGroupingManager()

    class Meta:
        db_table = "app_datagrouping"

    def __str__(self):
        return f"{self.name}"


class Tag(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.IntegerField(choices=TagType.choices, default=TagType.SOURCE)
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{dict(TagType.choices).get(self.type)}: {self.name}"


class DatasetReferenceCode(TimeStampedModel):
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code to identify the source (eg. DH for Data Hub, EW for Export Wins)",
    )
    description = models.TextField(null=True, blank=True)
    counter = models.IntegerField(default=0)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return self.code

    @transaction.atomic
    def get_next_reference_number(self):
        self.counter = F("counter") + 1
        self.save(update_fields=["counter"])
        self.refresh_from_db()
        return self.counter


class DataSetSubscriptionManager(models.Manager):
    def active(self, user):
        return self.filter(
            Q(notify_on_data_change=True) | Q(notify_on_schema_change=True), user=user
        )


class DataSetSubscription(TimeStampedUserModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.UUIDField(null=True)
    dataset = GenericForeignKey("content_type", "object_id")

    notify_on_schema_change = models.BooleanField(default=False)
    notify_on_data_change = models.BooleanField(default=False)

    objects = DataSetSubscriptionManager()

    class Meta:
        verbose_name = "DataSet Subscription"
        verbose_name_plural = "DataSet Subscriptions"
        unique_together = ["user", "object_id"]

    def __str__(self):
        return f"{self.user.email} {self.object_id}"

    def is_active(self):
        return self.notify_on_data_change or self.notify_on_schema_change

    def make_inactive(self):
        self.notify_on_data_change = False
        self.notify_on_schema_change = False

    def get_list_of_selected_options(self):
        selected = []

        if self.notify_on_data_change:
            selected.append("Each time data has been changed")

        if self.notify_on_schema_change:
            selected.append("Each time columns are added, removed or renamed")

        return selected


class DataSet(DeletableTimestampedUserModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.IntegerField(
        choices=[
            # pylint: disable=maybe-no-member
            (t, t.label)
            for t in [DataSetType.MASTER, DataSetType.DATACUT]
        ],
        default=DataSetType.DATACUT,
    )
    name = models.CharField(blank=False, null=False, max_length=128)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)
    short_description = models.CharField(blank=False, null=False, max_length=256)
    grouping = models.ForeignKey(DataGrouping, null=True, on_delete=models.CASCADE)
    description = RichTextField(null=False, blank=False)
    acronyms = models.CharField(blank=True, default="", max_length=255)
    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    licence = models.CharField(
        null=True, blank=True, max_length=256, help_text="Licence description"
    )
    licence_url = models.CharField(
        null=True, blank=True, max_length=1024, help_text="Link to license (optional)"
    )
    retention_policy = models.TextField(null=True, blank=True)
    personal_data = models.CharField(null=True, blank=True, max_length=128)
    restrictions_on_usage = models.TextField(null=True, blank=True)
    user_access_type = models.CharField(
        max_length=64,
        choices=UserAccessType.choices,
        default=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    published = models.BooleanField(default=False)
    published_at = models.DateField(null=True, blank=True)
    dictionary_published = models.BooleanField(default=False)
    eligibility_criteria = ArrayField(models.CharField(max_length=256), null=True)
    number_of_downloads = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField(Tag, related_name="+", blank=True)
    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_owned_datasets",
        null=True,
        blank=True,
    )
    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_managed_datasets",
        null=True,
        blank=True,
    )
    reference_code = models.ForeignKey(
        DatasetReferenceCode, null=True, blank=True, on_delete=models.SET_NULL
    )
    events = GenericRelation(EventLog)
    authorized_email_domains = ArrayField(
        models.CharField(max_length=256),
        blank=True,
        default=list,
        help_text="Comma-separated list of domain names without spaces, e.g trade.gov.uk,fco.gov.uk",
    )
    search_vector_english = SearchVectorField(null=True, blank=True)
    search_vector_english_name = SearchVectorField(null=True, blank=True)
    search_vector_english_short_description = SearchVectorField(null=True, blank=True)
    search_vector_english_tags = SearchVectorField(null=True, blank=True)
    search_vector_english_description = SearchVectorField(null=True, blank=True)

    subscriptions = GenericRelation(DataSetSubscription)

    average_unique_users_daily = models.FloatField(default=0)

    class Meta:
        db_table = "app_dataset"
        indexes = (GinIndex(fields=["search_vector_english"]),)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_reference_code = self.reference_code

    def __str__(self):
        return self.name

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.update_published_timestamp()

        acronyms = []
        for pairing in GRID_ACRONYM_MAP:
            if re.search(r"\b{}\b".format(pairing[1]), self.description, re.I) is not None:
                acronyms.append(pairing[0])
            if re.search(r"\b{}\b".format(pairing[0]), self.description, re.I) is not None:
                acronyms.append(pairing[1])

        self.acronyms = " ".join(acronyms)

        super().save(force_insert, force_update, using, update_fields)

        # If the model's reference code has changed as part of this update reset the reference
        # number for any associated sources. This will trigger the source to update it's reference
        # number inline with the new reference code (if any).
        if self.reference_code != self._original_reference_code:
            self._original_reference_code = self.reference_code
            for obj in self.related_objects():
                obj.reference_number = None
                obj.save()

        tag_names = " ".join([x.name for x in self.tags.all()])
        DataSet.objects.filter(id=self.id).update(
            search_vector_english=(
                SearchVector("name", weight="A", config="english")
                + SearchVector("short_description", weight="B", config="english")
                + SearchVector(models.Value(tag_names), weight="C", config="english")
                + SearchVector("description", weight="D", config="english")
                + SearchVector("acronyms", weight="D", config="english")
            ),
            search_vector_english_name=SearchVector("name", config="english"),
            search_vector_english_short_description=SearchVector(
                "short_description", config="english"
            ),
            search_vector_english_tags=SearchVector(models.Value(tag_names), config="english"),
            search_vector_english_description=SearchVector("description", config="english")
            + SearchVector("acronyms", config="english"),
        )

    def related_objects(self):
        """
        Returns a list of sources related to this dataset
        """
        RELATED_FIELDS = [
            "sourcetable",
            "sourceview",
            "sourcelink",
            "customdatasetquery",
        ]
        related = []
        for related_field in RELATED_FIELDS:
            related += [copy.copy(obj) for obj in getattr(self, related_field + "_set").all()]
        return related

    def related_datasets(self, order=None):
        if self.type == DataSetType.DATACUT:
            custom_queries = self.customdatasetquery_set.all().prefetch_related("tables")

            query_tables = []
            for query in custom_queries:
                query_tables.extend([qt.table for qt in query.tables.all()])

            ds_tables = [
                row.dataset
                for row in SourceTable.objects.filter(
                    dataset__published=True,
                    dataset__deleted=False,
                    table__in=query_tables,
                )
                .prefetch_related("dataset")
                .only("dataset")
                .distinct("dataset")
                .order_by("dataset", order or "dataset__name")
            ]

            return ds_tables

        elif self.type == DataSetType.MASTER:
            tables = self.sourcetable_set.all()

            if len(tables) > 0:
                filters = reduce(
                    operator.or_,
                    (Q(schema=table.schema, table=table.table) for table in tables),
                )
            else:
                filters = Q()

            datacuts = [
                row.query.dataset
                for row in CustomDatasetQueryTable.objects.filter(filters)
                .only("query__dataset")
                .distinct("query__dataset")
                .order_by("query__dataset", order or "query__dataset__name")
            ]

            return datacuts

        else:
            raise ValueError(f"Not implemented for {self.type}")

    def related_charts(self):
        # Group dataset visualisations and chart builder charts so they
        # can be shown on the same page
        fields = ["id", "name", "summary", "gds_phase_name", "type"]
        # pylint: disable=no-member
        return (
            self.charts.all()
            .annotate(type=models.Value("chart"))
            .values(*fields)
            .union(self.visualisations.live().annotate(type=models.Value("vega")).values(*fields))
        )

    def update_published_timestamp(self):
        if not self.published:
            return

        if not self.published_at:
            self.published_at = timezone.now()

    def user_has_access(self, user):
        user_email_domain = user.email.split("@")[1]
        return (
            self.user_access_type in [UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN]
            or self.datasetuserpermission_set.filter(user=user).exists()
            or user_email_domain in self.authorized_email_domains
        )

    def user_has_bookmarked(self, user):
        return self.datasetbookmark_set.filter(user=user).exists()

    def toggle_bookmark(self, user):
        if self.user_has_bookmarked(user):
            self.datasetbookmark_set.filter(user=user).delete()
        else:
            self.datasetbookmark_set.create(user=user)

    def set_bookmark(self, user):
        if self.user_has_bookmarked(user):
            return
        self.datasetbookmark_set.create(user=user)

    def unset_bookmark(self, user):
        if not self.user_has_bookmarked(user):
            return
        self.datasetbookmark_set.filter(user=user).delete()

    def bookmark_count(self):
        return self.datasetbookmark_set.count()

    def clone(self):
        """Create a copy of the dataset and any related objects.

        New dataset is unpublished and has a name prefixed with
        "Copy of <original dataset name>".

        The new datasets published_at date is set to the moment
        that it is published.

        Related objects (excluding user permissions) are duplicated
        for the new dataset.

        """

        clone = copy.copy(self)

        clone.pk = None
        clone.name = f"Copy of {self.name}"
        clone.slug = ""
        clone.number_of_downloads = 0
        clone.published = False
        clone.published_at = None
        clone.save()

        for obj in self.related_objects():
            obj.pk = None
            obj.reference_number = None
            obj.dataset = clone
            obj.save()

        return clone

    def get_admin_edit_url(self):
        if self.type == DataSetType.MASTER:
            return reverse("admin:datasets_masterdataset_change", args=(self.id,))
        return reverse("admin:datasets_datacutdataset_change", args=(self.id,))

    def get_absolute_url(self):
        return "{}#{}".format(reverse("datasets:dataset_detail", args=(self.id,)), self.slug)

    def get_usage_history_url(self):
        return reverse("datasets:usage_history", args=(self.id,))

    def get_related_source(self, source_id):
        for related_object in self.related_objects():
            if str(related_object.id) == str(source_id):
                return related_object
        return None


class DataSetVisualisation(DeletableTimestampedUserModel):
    name = models.CharField(max_length=255)
    summary = models.TextField()
    vega_definition_json = models.TextField()
    database = models.ForeignKey(Database, default=None, on_delete=models.CASCADE)
    query = models.TextField(null=True, blank=True)

    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name="visualisations")

    gds_phase_name = models.CharField(max_length=25, default="", blank=True)


class DataSetChartBuilderChart(TimeStampedUserModel):
    name = models.CharField(max_length=255)
    summary = models.TextField()
    chart = models.ForeignKey(ChartBuilderChart, on_delete=models.PROTECT, related_name="datasets")
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name="charts")
    gds_phase_name = models.CharField(max_length=25, default="", blank=True)

    def __str__(self):
        return self.name


class DataSetUserPermission(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_datasetuserpermission"
        unique_together = ("user", "dataset")


class DataSetBookmark(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_datasetbookmark"
        unique_together = ("user", "dataset")


class DataSetApplicationTemplatePermission(models.Model):
    application_template = models.ForeignKey(ApplicationTemplate, on_delete=models.CASCADE)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_datasetapplicationtemplatepermission"
        unique_together = ("dataset", "application_template")


class MasterDatasetManager(DeletableQuerySet):
    def get_queryset(self):
        return super().get_queryset().filter(type=DataSetType.MASTER)


class MasterDataset(DataSet):
    """
    Proxy model to allow to logically separate out "source" and "data cut" datasets in the admin.
    """

    objects = MasterDatasetManager()

    class Meta:
        proxy = True
        verbose_name = "Source Dataset"
        permissions = [
            (
                "manage_unpublished_master_datasets",
                "Manage (create, view, edit) unpublished source datasets",
            )
        ]


class MasterDatasetUserPermission(DataSetUserPermission):
    """
    Proxy model to allow for separate admin pages for master and data cut datasets
    """

    class Meta:
        proxy = True


class DataCutDatasetManager(DeletableQuerySet):
    def get_queryset(self):
        return super().get_queryset().filter(type=DataSetType.DATACUT)


class DataCutDataset(DataSet):
    """
    Proxy model to allow to logically separate out "master" and "data cut" datasets in the admin.
    """

    objects = DataCutDatasetManager()

    class Meta:
        proxy = True
        verbose_name = "Data Cut Dataset"
        permissions = [
            (
                "manage_unpublished_datacut_datasets",
                "Manage (create, view, edit) unpublished datacut datasets",
            )
        ]


class DataCutDatasetUserPermission(DataSetUserPermission):
    """
    Proxy model to allow for separate admin pages for master and data cut datasets
    """

    class Meta:
        proxy = True


class ReferenceNumberedDatasetSource(TimeStampedModel):
    """
    Abstract model that adds a reference number to a dataset source model.
    """

    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    reference_number = models.IntegerField(null=True)

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # If a reference code is set on the dataset, add a reference number to this source
        # by incrementing the counter on the reference code model
        if self.reference_number is None and self.dataset.reference_code is not None:
            self.reference_number = self.dataset.reference_code.get_next_reference_number()
        # If the dataset's reference code was unset, unset this source's reference number
        elif self.reference_number is not None and self.dataset.reference_code is None:
            self.reference_number = None
        super().save(force_insert, force_update, using, update_fields)

    @property
    def source_reference(self):
        if self.dataset.reference_code is not None and self.reference_number is not None:
            return "".join(
                [
                    self.dataset.reference_code.code.upper(),
                    str(self.reference_number).zfill(5),
                ]
            )
        return None

    def get_filename(self, extension=".csv"):
        filename = slugify(self.name) + extension  # pylint: disable=no-member
        if self.source_reference is not None:
            return f"{self.source_reference}-{filename}"
        return filename


class BaseSource(ReferenceNumberedDatasetSource):
    FREQ_DAILY = 1
    FREQ_WEEKLY = 2
    FREQ_MONTHLY = 3
    FREQ_QUARTERLY = 4
    FREQ_ANNUALLY = 5
    FREQ_6_MONTHLY = 6
    FREQ_ADHOC = 7
    _FREQ_CHOICES = (
        (FREQ_DAILY, "Daily"),
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
        (FREQ_QUARTERLY, "Quarterly"),
        (FREQ_6_MONTHLY, "6-monthly"),
        (FREQ_ANNUALLY, "Annually"),
        (FREQ_ADHOC, "Ad hoc"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=1024,
        blank=False,
        help_text="Used as the displayed text in the download link",
    )
    database = models.ForeignKey(Database, default=None, on_delete=models.CASCADE)
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
        default="public",
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
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )
    dataset_finder_opted_in = models.BooleanField(
        default=False,
        null=False,
        verbose_name="IAM/IAO opt-in for Dataset Finder",
        help_text=(
            "Should this dataset be discoverable through Dataset Finder for all users, "
            "even if they haven’t been explicitly granted access?"
        ),
    )
    data_grid_enabled = models.BooleanField(
        default=True,
        help_text="Allow users to filter, sort and export data from within the browser",
    )
    data_grid_download_enabled = models.BooleanField(
        default=False,
        help_text="Allow users to download from the data grid (requires a download limit)",
    )
    data_grid_download_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Set the maximum number of records that can be downloaded from the data grid "
            "(required if data grid download is enabled)"
        ),
    )

    class Meta:
        db_table = "app_sourcetable"

    def __str__(self):
        return f"{self.name} ({self.id})"

    def can_show_link_for_user(self, user):
        return False

    @property
    def type(self):
        return DataLinkType.SOURCE_TABLE

    def get_data_last_updated_date(self):
        return get_earliest_tables_last_updated_date(
            self.database.memorable_name, ((self.schema, self.table),)
        )

    def get_grid_data_url(self):
        return reverse("datasets:source_table_data", args=(self.dataset_id, self.id))

    def get_data_grid_query(self):
        return sql.SQL("SELECT * from {}.{}").format(
            sql.Identifier(self.schema), sql.Identifier(self.table)
        )

    def get_column_config(self):
        """
        Return column configuration for the source table in the format expected by ag-grid.
        """
        col_defs = []
        for column in datasets_db.get_columns(
            self.database.memorable_name,
            schema=self.schema,
            table=self.table,
            include_types=True,
        ):
            col_defs.append(
                {
                    "field": column[0],
                    "filter": True,
                    "sortable": True,
                    "dataType": GRID_DATA_TYPE_MAP.get(column[1], column[1]),
                }
            )
        return col_defs

    def get_column_details_url(self):
        return reverse(
            "datasets:source_table_column_details",
            args=(self.dataset_id, self.id),
        )

    def get_chart_builder_url(self):
        return reverse(
            "charts:create-chart-from-source-table",
            args=(self.id,),
        )

    def get_chart_builder_query(self):
        return f"SELECT * from {self.schema}.{self.table}"

    def get_previous_uploads(self):
        return UploadedTable.objects.filter(schema=self.schema, table_name=self.table).order_by(
            "-data_flow_execution_date"
        )


class SourceTableFieldDefinition(models.Model):
    field = models.CharField(
        max_length=63,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )
    description = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
    )
    source_table = models.ForeignKey(
        SourceTable, on_delete=models.CASCADE, related_name="field_definitions"
    )


class SourceView(BaseSource):
    view = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )

    def get_absolute_url(self):
        return reverse("datasets:dataset_source_view_download", args=(self.dataset.id, self.id))

    def can_show_link_for_user(self, user):
        return True

    @property
    def type(self):
        return DataLinkType.SOURCE_VIEW


class SourceLink(ReferenceNumberedDatasetSource):
    TYPE_EXTERNAL = 1
    TYPE_LOCAL = 2
    _LINK_TYPES = ((TYPE_EXTERNAL, "External Link"), (TYPE_LOCAL, "Local Link"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link_type = models.IntegerField(choices=_LINK_TYPES, default=TYPE_EXTERNAL)
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
        help_text="Used as the displayed text in the download link",
    )
    url = models.CharField(max_length=256)
    format = models.CharField(blank=False, null=False, max_length=10)
    frequency = models.CharField(blank=False, null=False, max_length=50)

    class Meta:
        db_table = "app_sourcelink"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current link type so it can be compared on save
        self._original_url = self.url

    def __str__(self):
        return self.name

    def _is_s3_link(self):
        return self.url.startswith("s3://")

    def get_frequency_display(self):
        return self.frequency

    def local_file_is_accessible(self):
        """
        Check whether we can access the file on s3
        :return:
        """
        client = get_s3_client()
        try:
            client.head_object(Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url)
        except ClientError:
            return False
        return True

    def _delete_s3_file(self):
        if self.url.startswith("s3://sourcelink") and self.local_file_is_accessible():
            client = get_s3_client()
            client.delete_object(Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # Allow users to change a url from local to external and vice versa
        is_s3_link = self._is_s3_link()
        was_s3_link = self._original_url.startswith("s3://")
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
        return reverse("datasets:dataset_source_link_download", args=(self.dataset_id, self.id))

    def get_preview_url(self):
        return reverse("datasets:data_cut_source_link_preview", args=(self.dataset_id, self.id))

    def show_column_filter(self):
        # this will be enabled in subsequent PR
        return False

    def can_show_link_for_user(self, user):
        return True

    def get_filename(self):  # pylint: disable=arguments-differ
        if self.link_type == self.TYPE_LOCAL:
            native_extension = os.path.splitext(self.url)[1]
            extension = native_extension if native_extension else ".csv"
            return super().get_filename(extension=extension)

        return super().get_filename()

    @property
    def type(self):
        return DataLinkType.SOURCE_LINK

    def get_data_last_updated_date(self):
        if self.link_type == self.TYPE_LOCAL:
            try:
                metadata = get_s3_client().head_object(
                    Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url
                )
                return metadata.get("LastModified")
            except ClientError:
                pass
        return None

    def user_can_preview(self, user):
        return self.dataset.user_has_access(user)

    def get_preview_data(self):
        """
        Returns column names and preview data for an s3 hosted csv.
        """
        if (
            not self._is_s3_link()
            or not self.local_file_is_accessible()
            or not self.url.endswith(".csv")
        ):
            return None, []

        client = get_s3_client()

        # Only read a maximum of 100Kb in for preview purposes. This should stop us getting
        # denial-of-service'd by files with a massive amount of data in the first few columns
        file = client.get_object(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key=self.url, Range="bytes=0-102400"
        )
        head = file["Body"].read().decode("utf-8")
        # Drop anything after the rightmost newline in case we only got a partial row
        head = head[: head.rindex("\n") + 1]
        csv_data = head.splitlines()
        del csv_data[settings.DATASET_PREVIEW_NUM_OF_ROWS :]
        fh = StringIO("\n".join(csv_data))
        reader = csv.DictReader(fh)
        records = []
        for row in reader:
            records.append(row)
            if len(records) >= settings.DATASET_PREVIEW_NUM_OF_ROWS:
                break

        return reader.fieldnames, records


class CustomDatasetQuery(ReferenceNumberedDatasetSource):
    FREQ_DAILY = 1
    FREQ_WEEKLY = 2
    FREQ_MONTHLY = 3
    FREQ_QUARTERLY = 4
    FREQ_ANNUALLY = 5
    _FREQ_CHOICES = (
        (FREQ_DAILY, "Daily"),
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
        (FREQ_QUARTERLY, "Quarterly"),
        (FREQ_ANNUALLY, "Annually"),
    )
    name = models.CharField(max_length=255)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    query = models.TextField()
    frequency = models.IntegerField(choices=_FREQ_CHOICES)
    reviewed = models.BooleanField(default=False)
    data_grid_enabled = models.BooleanField(
        default=False,
        help_text="Allow users to filter, sort and export data from within the browser",
    )

    class Meta:
        verbose_name = "SQL Query"
        verbose_name_plural = "SQL Queries"

    def __str__(self):
        return f"{self.dataset.name}: {self.name}"

    def get_absolute_url(self):
        return reverse("datasets:dataset_query_download", args=(self.dataset_id, self.id))

    def get_preview_url(self):
        return reverse("datasets:data_cut_query_preview", args=(self.dataset_id, self.id))

    def show_column_filter(self):
        return True

    def can_show_link_for_user(self, user):
        if user.is_superuser:
            return True

        return self.reviewed

    @property
    def type(self):
        return DataLinkType.CUSTOM_QUERY

    def get_data_last_updated_date(self):
        tables = CustomDatasetQueryTable.objects.filter(query=self)
        if tables:
            return get_earliest_tables_last_updated_date(
                self.database.memorable_name,
                tuple((table.schema, table.table) for table in tables),
            )
        return None

    def user_can_preview(self, user):
        return self.dataset.user_has_access(user) and (self.reviewed or user.is_superuser)

    def get_preview_data(self):
        from dataworkspace.apps.core.utils import (  # pylint: disable=cyclic-import,import-outside-toplevel
            get_random_data_sample,
        )

        database_name = self.database.memorable_name
        columns = datasets_db.get_columns(database_name, query=self.query)
        records = []
        sample_size = settings.DATASET_PREVIEW_NUM_OF_ROWS
        if columns:
            rows = get_random_data_sample(
                self.database.memorable_name,
                sql.SQL(self.query),
                sample_size,
            )
            for row in rows:
                record_data = {}
                for i, column in enumerate(columns):
                    record_data[column] = row[i]
                records.append(record_data)
        return columns, records

    def get_grid_data_url(self):
        return reverse("datasets:custom_dataset_query_data", args=(self.dataset_id, self.id))

    @property
    def cleaned_query(self):
        # Replace any single '%' with '%%'
        return re.sub("(?<!%)%(?!%)", "%%", self.query).rstrip().rstrip(";")

    def get_data_grid_query(self):
        return sql.SQL(self.cleaned_query)

    def get_column_config(self):
        """
        Return column configuration for the query in the format expected by ag-grid.
        """
        col_defs = []
        for column in datasets_db.get_columns(
            self.database.memorable_name,
            query=self.cleaned_query,
            include_types=True,
        ):
            col_defs.append(
                {
                    "field": column[0],
                    "filter": True,
                    "sortable": True,
                    "dataType": GRID_DATA_TYPE_MAP.get(column[1], column[1]),
                }
            )
        return col_defs

    @property
    def data_grid_download_enabled(self):
        return True

    @property
    def data_grid_download_limit(self):
        return None

    def get_column_details_url(self):
        return reverse(
            "datasets:custom_query_column_details",
            args=(self.dataset_id, self.id),
        )

    def get_chart_builder_url(self):
        return reverse(
            "charts:create-chart-from-data-cut-query",
            args=(self.id,),
        )

    def get_chart_builder_query(self):
        return self.query


class CustomDatasetQueryTable(models.Model):
    query = models.ForeignKey(CustomDatasetQuery, on_delete=models.CASCADE, related_name="tables")
    table = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
        default="public",
    )


class ReferenceDataset(DeletableTimestampedUserModel):
    SORT_DIR_ASC = 1
    SORT_DIR_DESC = 2
    _SORT_DIR_CHOICES = ((SORT_DIR_ASC, "Ascending"), (SORT_DIR_DESC, "Descending"))
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    is_joint_dataset = models.BooleanField(default=False)  # No longer used
    is_draft = models.BooleanField(default=False)
    group = models.ForeignKey(DataGrouping, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    table_name = models.CharField(
        verbose_name="Table name",
        max_length=255,
        unique=True,
        help_text="Descriptive table name for the field - Note: Must start with "
        '"ref_" and contain only lowercase letters, numbers and underscores',
        validators=[
            RegexValidator(
                regex=r"^ref_[a-z0-9_]*$",
                message='Table names must be prefixed with "ref_" and can contain only '
                "lowercase letters, numbers and underscores",
            )
        ],
    )
    slug = models.SlugField()
    short_description = models.CharField(max_length=255)
    description = RichTextField(null=True, blank=True)
    acronyms = models.CharField(blank=True, default="", max_length=255)
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
        help_text="Name of the analysts database to keep in " "sync with this reference dataset",
    )
    sort_field = models.ForeignKey(
        "ReferenceDatasetField",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The field to order records by in any outputs. "
        "If not set records will be sorted by last updated date.",
    )
    sort_direction = models.IntegerField(default=SORT_DIR_ASC, choices=_SORT_DIR_CHOICES)
    number_of_downloads = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField(Tag, related_name="+", blank=True)
    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_owned_reference_datasets",
        null=True,
        blank=True,
    )
    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_managed_reference_datasets",
        null=True,
        blank=True,
    )

    licence_url = models.CharField(
        null=True, blank=True, max_length=1024, help_text="Link to license (optional)"
    )

    # Used as a parallel to DataSet.type, which will help other parts of the codebase
    # easily distinguish between reference datasets, datacuts, master datasets and visualisations.
    type = DataSetType.REFERENCE
    search_vector_english = SearchVectorField(null=True, blank=True)
    search_vector_english_name = SearchVectorField(null=True, blank=True)
    search_vector_english_short_description = SearchVectorField(null=True, blank=True)
    search_vector_english_tags = SearchVectorField(null=True, blank=True)
    search_vector_english_description = SearchVectorField(null=True, blank=True)

    subscriptions = GenericRelation(DataSetSubscription)

    average_unique_users_daily = models.FloatField(default=0)

    events = GenericRelation(EventLog)

    class Meta:
        db_table = "app_referencedataset"
        verbose_name = "Reference dataset"
        permissions = [
            (
                "manage_unpublished_reference_datasets",
                "Manage (create, view, edit) unpublished reference datasets",
            )
        ]
        indexes = (GinIndex(fields=["search_vector_english"]),)

    def __str__(self):
        return self.name

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

    @property
    def dictionary_published(self):
        return True

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

    def send_post_data_url(self):
        return reverse("datasets:reference_dataset_download", args=(self.uuid, "csv"))

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
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
                self._create_external_database_table(self.external_database.memorable_name)
        else:
            if self.external_database != self._original_ext_db:
                # If external db has been changed delete the original table
                if self._original_ext_db is not None:
                    self._drop_external_database_table(self._original_ext_db.memorable_name)
                # if external db is now set create the table and sync existing records
                if self.external_database is not None:
                    self._create_external_database_table(self.external_database.memorable_name)
                    self.sync_to_external_database(self.external_database.memorable_name)

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

        tag_names = " ".join([x.name for x in self.tags.all()])
        ReferenceDataset.objects.filter(id=self.id).update(
            search_vector_english=(
                SearchVector("name", weight="A", config="english")
                + SearchVector("short_description", weight="B", config="english")
                + SearchVector(models.Value(tag_names), weight="C", config="english")
                + SearchVector("description", weight="D", config="english")
                + SearchVector("acronyms", weight="D", config="english")
            ),
            search_vector_english_name=SearchVector("name", config="english"),
            search_vector_english_short_description=SearchVector(
                "short_description", config="english"
            ),
            search_vector_english_tags=SearchVector(models.Value(tag_names), config="english"),
            search_vector_english_description=SearchVector("description", config="english")
            + SearchVector("acronyms", config="english"),
        )

    @transaction.atomic
    def delete(self, **kwargs):  # pylint: disable=arguments-differ
        # Do not allow deletion if this dataset is referenced by other datasets
        linking_fields = ReferenceDatasetField.objects.filter(
            linked_reference_dataset_field__reference_dataset=self
        )
        if linking_fields.count() > 0:
            raise ProtectedError(
                "Cannot delete reference dataset as it is linked to by other datasets",
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
        Returns related ReferenceDatasetFields that are user editable.

        This uses dict comprehension as there may be multiple fields of
        type DATA_TYPE_FOREIGN_KEY pointing to the same reference dataset
        and we are only concerned with the relationship name rather than
        the individual field names
        :return:
        """
        return {
            f.name
            if f.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            else f.relationship_name: f
            for f in self.fields.filter(data_type__in=ReferenceDatasetField.EDITABLE_DATA_TYPES)
        }

    @property
    def column_names(self) -> List[str]:
        """
        Returns the column name for all associated fields.
        :return: list of field names
        """
        return [x.column_name for x in self.fields.all()]

    @property
    def identifier_field(self) -> "ReferenceDatasetField":
        """
        Returns the associated `ReferenceDataField` with `is_identifier`=True
        :return:
        """
        return self.fields.get(is_identifier=True)

    @property
    def display_name_field(self) -> "ReferenceDatasetField":
        """
        Returns the associated `ReferenceDataField` with `is_display_name`=True.
        Falls back to the identifier field if no display name is set.

        This is used in the DynamicReferenceDatasetRecordForm to display foreign
        key choices

        :return:
        """
        try:
            return self.fields.get(is_display_name=True)
        except ReferenceDatasetField.DoesNotExist:
            return self.fields.get(is_identifier=True)

    @property
    def export_field_names(self) -> List[str]:
        """
        Returns the field names for download files
        :return: list of display field names
        """
        return [f.name for f in self.fields.all()]

    @property
    def data_last_updated(self):
        """
        Return the most recent date a record was updated in the dataset
        :return:
        """
        records = self.get_records()
        if records.exists():
            return records.latest("updated_date").updated_date
        return None

    @property
    def version(self):
        return "{}.{}".format(self.major_version, self.minor_version)

    @property
    def published_version(self):
        return "{}.{}".format(self.published_major_version, self.published_minor_version)

    @property
    def record_sort_order(self):
        """
        Return ordering tuple for reference dataset records.
        If column type is foreign key sort on display name for the related model.
        :return:
        """
        prefix = "-" if self.sort_direction == self.SORT_DIR_DESC else ""
        order = "updated_date"
        if self.sort_field is not None:
            field = self.sort_field
            order = field.column_name
            if field.data_type == field.DATA_TYPE_FOREIGN_KEY:
                order = "{}__{}".format(
                    field.relationship_name,
                    field.linked_reference_dataset_field.column_name,
                )
        return ["".join([prefix, order])]

    def get_record_model_class(self) -> object:
        """
        Dynamically build a model class to represent a record in a dataset.
        If the class has been registered previously remove it from the cache before recreating.
        :return: dynamic model class
        """
        try:
            model = apps.all_models["datasets"][self.table_name]
        except KeyError:
            pass
        else:
            if model.__schema_version__ == self.schema_version:
                return model

        try:
            del apps.all_models["datasets"][self.table_name]
        except KeyError:
            pass

        class Meta:
            app_label = "datasets"
            db_table = self.table_name
            ordering = self.record_sort_order

        attrs = {
            **{
                f.column_name
                if f.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
                else f.relationship_name: f.get_model_field()
                for f in self.fields.all()
            },
            "__module__": "datasets",
            "__schema_version__": self.schema_version,
            "Meta": Meta,
        }

        # During the above DB queries, another request may have created and
        # registered the model. Ensure we don't attempt to register another one
        # since Django will raise an exception
        try:
            return apps.all_models["datasets"][self.table_name]
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
        return self._get_record("id", internal_id)

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
    def save_record(self, internal_id: Optional[int], form_data: dict, sync_externally=True):
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
            records.update(**form_data, updated_date=timezone.now())
            record = records.first()
        self.increment_minor_version()
        if sync_externally and self.external_database is not None:
            self.sync_to_external_database(self.external_database.memorable_name)
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
            self.sync_to_external_database(self.external_database.memorable_name)
        self.modified_date = datetime.utcnow()
        self.save()

    @transaction.atomic
    def delete_all_records(self):
        """
        Delete all records from the reference dataset table
        :return:
        """
        self.increment_minor_version()
        self.get_records().delete()
        if self.external_database is not None:
            self.sync_to_external_database(self.external_database.memorable_name)
        self.modified_date = datetime.utcnow()
        self.save()

    def sync_to_external_database(self, external_database):
        """
        Run a full sync of records from the local django db to `external_database`
        :param external_database:
        :return:
        """
        model_class = self.get_record_model_class()
        saved_ids = []

        for record in self.get_records():
            record_data = {}
            for field in self.fields.all():
                if field.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    record_data[field.column_name] = getattr(record, field.column_name)
                else:
                    record_data[field.relationship_name] = getattr(record, field.relationship_name)

            if model_class.objects.using(external_database).filter(pk=record.id).exists():
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).filter(pk=record.id).update(**record_data)
            else:
                with external_model_class(model_class) as mc:
                    mc.objects.using(external_database).create(
                        id=record.id, reference_dataset_id=self.id, **record_data
                    )
            saved_ids.append(record.id)

        with external_model_class(model_class) as mc:
            mc.objects.using(external_database).exclude(pk__in=saved_ids).delete()

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
            return ["default", self.external_database.memorable_name]
        return ["default"]

    def get_absolute_url(self):
        return "{}#{}".format(reverse("datasets:dataset_detail", args=(self.uuid,)), self.slug)

    def get_admin_edit_url(self):
        return reverse("admin:datasets_referencedataset_change", args=(self.id,))

    @staticmethod
    def get_type_display():
        """
        Allow for reference dataset type name display in api responses to match datasets.
        """
        return "Reference Dataset"

    def user_has_bookmarked(self, user):
        return self.referencedatasetbookmark_set.filter(user=user).exists()

    def toggle_bookmark(self, user):
        if self.user_has_bookmarked(user):
            self.referencedatasetbookmark_set.filter(user=user).delete()
        else:
            self.referencedatasetbookmark_set.create(user=user)

    def set_bookmark(self, user):
        if self.user_has_bookmarked(user):
            return
        self.referencedatasetbookmark_set.create(user=user)

    def unset_bookmark(self, user):
        if not self.user_has_bookmarked(user):
            return
        self.referencedatasetbookmark_set.filter(user=user).delete()

    def bookmark_count(self):
        return self.referencedatasetbookmark_set.count()

    def get_column_config(self):
        """
        Return column configuration for the reference dataset in the
        format expected by ag-grid.
        """
        col_defs = []
        for field in self.fields.all():
            column_name = (
                field.column_name
                if field.data_type != field.DATA_TYPE_FOREIGN_KEY
                else f"{field.relationship_name}_{field.linked_reference_dataset_field.column_name}"
            )
            data_type = (
                field.data_type
                if field.data_type != field.DATA_TYPE_FOREIGN_KEY
                else field.linked_reference_dataset_field.data_type
            )
            col_def = {
                "headerName": field.name,
                "field": column_name,
                "sortable": True,
                "filter": "agTextColumnFilter",
            }
            if data_type in [
                field.DATA_TYPE_INT,
                field.DATA_TYPE_FLOAT,
            ]:
                col_def["filter"] = "agNumberColumnFilter"
            elif data_type in [field.DATA_TYPE_DATE, field.DATA_TYPE_DATETIME]:
                col_def["filter"] = "agDateColumnFilter"
            col_defs.append(col_def)
        return col_defs

    def get_grid_data(self):
        """
        Return all records of this reference dataset in a JSON
        serializable format for use by ag-grid.
        """
        records = []
        for record in self.get_records():
            record_data = {}
            for field in self.fields.all():
                if field.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    record_data[field.column_name] = getattr(record, field.column_name)
                    # ISO format dates for js compatibility
                    if isinstance(record_data[field.column_name], datetime):
                        record_data[field.column_name] = record_data[field.column_name].isoformat()
                else:
                    relationship = getattr(record, field.relationship_name)
                    record_data[
                        f"{field.relationship_name}_{field.linked_reference_dataset_field.column_name}"
                    ] = (
                        getattr(
                            relationship,
                            field.linked_reference_dataset_field.column_name,
                        )
                        if relationship
                        else None
                    )
            records.append(record_data)
        return records

    def get_metadata_table_hash(self):
        """
        Hash reference dataset records as the user would see them. This allows
        us to include linked dataset fields in the hash.
        """
        hashed_data = hashlib.md5()
        for record in self.get_records():
            data = {}
            for field in self.fields.all():
                if field.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    data[field.column_name] = str(getattr(record, field.column_name))
                else:
                    relationship = getattr(record, field.relationship_name)
                    data[field.linked_reference_dataset_field.column_name] = (
                        str(
                            getattr(
                                relationship,
                                field.linked_reference_dataset_field.column_name,
                            )
                        )
                        if relationship
                        else None
                    )
            hashed_data.update(json.dumps(data).encode("utf-8"))
        return hashed_data.digest()


class ReferenceDataSetBookmark(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    reference_dataset = models.ForeignKey(ReferenceDataset, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_referencedatasetbookmark"
        unique_together = ("user", "reference_dataset")


class ReferenceDatasetRecordBase(models.Model):
    reference_dataset = models.ForeignKey(
        ReferenceDataset, on_delete=models.CASCADE, related_name="records"
    )
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return str(getattr(self, self.reference_dataset.display_name_field.column_name, None))


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
    _DATA_TYPES = (
        (DATA_TYPE_CHAR, "Character field"),
        (DATA_TYPE_INT, "Integer field"),
        (DATA_TYPE_FLOAT, "Float field"),
        (DATA_TYPE_DATE, "Date field"),
        (DATA_TYPE_TIME, "Time field"),
        (DATA_TYPE_DATETIME, "Datetime field"),
        (DATA_TYPE_BOOLEAN, "Boolean field"),
        (DATA_TYPE_FOREIGN_KEY, "Linked Reference Dataset field"),
        (DATA_TYPE_UUID, "Universal unique identifier field"),
    )
    DATA_TYPE_MAP = {
        DATA_TYPE_CHAR: "varchar(255)",
        DATA_TYPE_INT: "integer",
        DATA_TYPE_FLOAT: "float",
        DATA_TYPE_DATE: "date",
        DATA_TYPE_TIME: "time",
        DATA_TYPE_DATETIME: "timestamp",
        DATA_TYPE_BOOLEAN: "boolean",
        DATA_TYPE_FOREIGN_KEY: "integer",
        DATA_TYPE_UUID: "uuid",
    }
    POSTGRES_TYPE_MAP = {
        DATA_TYPE_CHAR: 18,
        DATA_TYPE_INT: 23,
        DATA_TYPE_FLOAT: 700,
        DATA_TYPE_DATE: 1082,
        DATA_TYPE_TIME: 1083,
        DATA_TYPE_DATETIME: 1114,
        DATA_TYPE_BOOLEAN: 16,
        DATA_TYPE_FOREIGN_KEY: 23,
        DATA_TYPE_UUID: 2950,
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
    reference_dataset = models.ForeignKey(
        ReferenceDataset, on_delete=models.CASCADE, related_name="fields"
    )
    data_type = models.IntegerField(choices=_DATA_TYPES)
    is_identifier = models.BooleanField(
        default=False, help_text="This field is the unique identifier for the record"
    )
    is_display_name = models.BooleanField(
        default=False,
        help_text="This field is the name that will be displayed in the upload "
        "record form when referenced by other datasets",
    )
    name = models.CharField(max_length=255, help_text="The display name for the field")
    column_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Descriptive name for the field. This name is used in the Data Workspace "
        "database. Leave blank for linked reference dataset fields",
        validators=[
            RegexValidator(
                regex=r"^[a-z][a-z0-9_\.]*$",
                message="Column names must be lowercase and must "
                "start with a letter and contain only "
                "letters, numbers, underscores and full stops.",
            )
        ],
    )
    description = models.TextField(blank=True, null=True)
    required = models.BooleanField(default=False)
    linked_reference_dataset = models.ForeignKey(
        ReferenceDataset,
        on_delete=models.PROTECT,
        related_name="linked_fields",
        null=True,
        blank=True,
    )  # No longer used
    linked_reference_dataset_field = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="linked_dataset_fields",
        null=True,
        blank=True,
    )
    relationship_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="For use with linked reference dataset fields only. Give a name for the "
        'linked reference dataset, which will be appended with "_id" to form a foreign key '
        "in the database table. Where multiple fields are selected from the same linked "
        "reference dataset, the same name should be used",
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$",
                message="Relationship names must start with a letter and contain only "
                "letters, numbers, underscores and full stops.",
            )
        ],
    )
    sort_order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        db_table = "app_referencedatasetfield"
        unique_together = (
            ("reference_dataset", "name"),
            ("reference_dataset", "column_name"),
        )
        verbose_name = "Reference dataset field"
        ordering = ("sort_order",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stash the current data type and name so they can be compared on save
        self._original_data_type = self.data_type
        self._original_column_name = self.column_name

    def __str__(self):
        return "{}: {}".format(self.reference_dataset.name, self.name)

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
                if self.data_type != self.DATA_TYPE_FOREIGN_KEY:
                    editor.add_field(model_class, model_class._meta.get_field(self.column_name))
                else:
                    editor.add_field(
                        model_class,
                        model_class._meta.get_field(self.relationship_name),
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
                    editor.alter_field(model_class, from_field, to_field)

    def _update_db_column_data_type(self):
        super().save()
        self.reference_dataset.increment_schema_version()
        for database in self.reference_dataset.get_database_names():
            with connections[database].cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        """
                        ALTER TABLE {table_name}
                        ALTER COLUMN {column_name} TYPE {data_type}
                        USING {column_name}::text::{data_type}
                        """
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

        # Ensure a reference dataset field cannot link to a field that is itself linked
        # to another reference dataset field
        if (
            self.linked_reference_dataset_field
            and self.linked_reference_dataset_field.data_type == self.DATA_TYPE_FOREIGN_KEY
        ):
            raise ValidationError(
                "Unable to link reference dataset fields to another field that is itself linked"
            )

        # Ensure a reference dataset field cannot link to a field in a dataset that has a
        # linked field pointing to a field in the current dataset (circular link)
        circular_reference_datasets = ReferenceDatasetField.objects.filter(
            linked_reference_dataset_field__reference_dataset=self.reference_dataset
        ).values_list("reference_dataset_id", flat=True)
        if (
            self.linked_reference_dataset_field
            and self.linked_reference_dataset_field.reference_dataset.id
            in circular_reference_datasets
        ):
            raise ValidationError(
                "Unable to link reference dataset fields to another field that points back to this dataset (circular link)"
            )

        # If this is a newly created field add it to the db
        if self.id is None:
            # For linked reference dataset fields, the foreign key column to be
            # added is derived from the field's relationship_name. As we allow
            # multiple fields with the same relationship_name, the column may
            # already exist so we catch the database error.
            try:
                with transaction.atomic():
                    self._add_column_to_db()
            except DatabaseError:
                pass
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
        model_class = self.reference_dataset.get_record_model_class()
        for database in self.reference_dataset.get_database_names():
            with connections[database].schema_editor() as editor:
                if self.data_type != self.DATA_TYPE_FOREIGN_KEY:
                    editor.remove_field(
                        model_class,
                        model_class._meta.get_field(self._original_column_name),
                    )
                else:
                    # Don't delete the relationship if there are other fields still referencing it
                    if (
                        self.reference_dataset.fields.filter(
                            relationship_name=self.relationship_name
                        )
                        .exclude(id=self.id)
                        .count()
                    ):
                        continue
                    editor.remove_field(
                        model_class,
                        model_class._meta.get_field(self.relationship_name),
                    )

        # Remove reference dataset sort field if it is set to this field
        if self.reference_dataset.sort_field == self:
            self.reference_dataset.sort_field = None
            self.reference_dataset.save()

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
        field_data = {"label": self.name}
        if self.data_type == self.DATA_TYPE_DATE:
            field_data["widget"] = forms.DateInput(attrs={"type": "date"})
            field_data["input_formats"] = (
                "%Y-%m-%d",
                "%d-%m-%Y",
                "%y-%m-%d",
                "%d-%m-%y",
                "%d/%m/%Y",
                "%d/%m/%y",
            )
        elif self.data_type == self.DATA_TYPE_TIME:
            field_data["widget"] = forms.DateInput(attrs={"type": "time"})
        elif self.data_type == self.DATA_TYPE_FOREIGN_KEY:
            field_data[
                "queryset"
            ] = self.linked_reference_dataset_field.reference_dataset.get_records()
            field_data["label"] = self.relationship_name_for_record_forms
        field_data["required"] = self.is_identifier or self.required
        field = self._DATA_TYPE_FORM_FIELD_MAP.get(self.data_type)(**field_data)
        field.widget.attrs["required"] = field.required
        return field

    def get_model_field(self):
        """
        Instantiates a django model field based on this models selected `data_type`.
        :return:
        """
        model_field = self._DATA_TYPE_MODEL_FIELD_MAP.get(self.data_type)
        model_config = {
            "verbose_name": self.name,
            "blank": not self.is_identifier and not self.required,
            "null": not self.is_identifier and not self.required,
            "max_length": 255,
        }
        if self.data_type == self.DATA_TYPE_FOREIGN_KEY:
            model_config.update(
                {
                    "verbose_name": "Linked Reference Dataset field",
                    "to": self.linked_reference_dataset_field.reference_dataset.get_record_model_class(),
                    "on_delete": models.DO_NOTHING,
                }
            )
        elif self.data_type == self.DATA_TYPE_UUID:
            model_config.update({"default": uuid.uuid4, "editable": False})
        return model_field(**model_config)

    @property
    def relationship_name_for_record_forms(self):
        """
        When editing and uploading csv's for records, the label for foreign
        key relationships should ideally be the relationship name but this is
        often set as a cryptic name when creating the linked fields, e.ig field_01.

        Instead the string before the colon in the field name is returned.
        If there is no colon, the relationship name is returned.
        """
        if self.data_type != self.DATA_TYPE_FOREIGN_KEY:
            return None

        if ":" in self.name:
            # pylint: disable=use-maxsplit-arg
            return self.name.split(":")[0]
        return self.relationship_name


class ReferenceDatasetUploadLog(TimeStampedUserModel):
    reference_dataset = models.ForeignKey(ReferenceDataset, on_delete=models.CASCADE)

    class Meta:
        ordering = ("created_date",)

    def additions(self):
        return self.records.filter(status=ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED)

    def updates(self):
        return self.records.filter(status=ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_UPDATED)

    def errors(self):
        return self.records.filter(status=ReferenceDatasetUploadLogRecord.STATUS_FAILURE)


class ReferenceDatasetUploadLogRecord(TimeStampedModel):
    STATUS_SUCCESS_ADDED = 1
    STATUS_SUCCESS_UPDATED = 2
    STATUS_FAILURE = 3
    _STATUS_CHOICES = (
        (STATUS_SUCCESS_ADDED, "Record added successfully"),
        (STATUS_SUCCESS_UPDATED, "Record updated successfully"),
        (STATUS_FAILURE, "Record upload failed"),
    )
    upload_log = models.ForeignKey(
        ReferenceDatasetUploadLog, on_delete=models.CASCADE, related_name="records"
    )
    status = models.IntegerField(choices=_STATUS_CHOICES)
    row_data = models.JSONField()
    errors = models.JSONField(null=True)

    class Meta:
        ordering = ("created_date",)

    def __str__(self):
        return "{}: {}".format(self.created_date, self.get_status_display())


class VisualisationCatalogueItem(DeletableTimestampedUserModel):
    objects = DeletableQuerySet()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visualisation_template = models.OneToOneField(
        VisualisationTemplate, on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=255, null=False, blank=False)
    slug = models.SlugField(max_length=50, db_index=True, unique=True, null=False, blank=False)
    tags = models.ManyToManyField(Tag, related_name="+", blank=True)
    short_description = models.CharField(max_length=255)
    description = RichTextField(null=True, blank=True)
    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    secondary_enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    licence = models.CharField(null=False, blank=True, max_length=256)
    retention_policy = models.TextField(null=True, blank=True)
    personal_data = models.CharField(null=True, blank=True, max_length=128)
    restrictions_on_usage = models.TextField(null=True, blank=True)
    published = models.BooleanField(default=False)

    published_at = models.DateField(null=True, blank=True)
    updated_at = models.DateField(null=True, blank=True)

    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_owned_visualisations",
        null=True,
        blank=True,
    )
    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_managed_visualisations",
        null=True,
        blank=True,
    )
    eligibility_criteria = ArrayField(models.CharField(max_length=256), null=True)
    user_access_type = models.CharField(
        max_length=64,
        choices=UserAccessType.choices,
        default=UserAccessType.REQUIRES_AUTHENTICATION,
    )
    events = GenericRelation(EventLog)
    datasets = models.ManyToManyField(DataSet, related_name="related_visualisations", blank=True)

    # Used as a parallel to DataSet.type, which will help other parts of the codebase
    # easily distinguish between reference datasets, datacuts, master datasets and visualisations.
    type = DataSetType.VISUALISATION
    authorized_email_domains = ArrayField(
        models.CharField(max_length=256),
        blank=True,
        default=list,
        help_text="Comma-separated list of domain names without spaces, e.g trade.gov.uk,fco.gov.uk",
    )

    licence_url = models.CharField(
        null=True, blank=True, max_length=1024, help_text="Link to license (optional)"
    )
    average_unique_users_daily = models.FloatField(default=0)
    search_vector_english = SearchVectorField(null=True, blank=True)
    search_vector_english_name = SearchVectorField(null=True, blank=True)
    search_vector_english_short_description = SearchVectorField(null=True, blank=True)
    search_vector_english_tags = SearchVectorField(null=True, blank=True)
    search_vector_english_description = SearchVectorField(null=True, blank=True)

    class Meta:
        permissions = [
            (
                "manage_unpublished_visualisations",
                "Manage (create, view, edit) unpublished visualisations",
            )
        ]
        indexes = (GinIndex(fields=["search_vector_english"]),)

    def get_admin_edit_url(self):
        return reverse("admin:datasets_visualisationcatalogueitem_change", args=(self.id,))

    def get_absolute_url(self):
        return "{}#{}".format(reverse("datasets:dataset_detail", args=(self.id,)), self.slug)

    def update_published_and_updated_timestamps(self):
        if not self.published:
            return

        if not self.published_at:
            self.published_at = timezone.now()

        self.updated_at = timezone.now()

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.update_published_and_updated_timestamps()
        super().save(force_insert, force_update, using, update_fields)

        tag_names = " ".join([x.name for x in self.tags.all()])
        VisualisationCatalogueItem.objects.filter(id=self.id).update(
            search_vector_english=(
                SearchVector("name", weight="A", config="english")
                + SearchVector("short_description", weight="B", config="english")
                + SearchVector(models.Value(tag_names), weight="C", config="english")
                + SearchVector("description", weight="D", config="english")
            ),
            search_vector_english_name=SearchVector("name", config="english"),
            search_vector_english_short_description=SearchVector(
                "short_description", config="english"
            ),
            search_vector_english_tags=SearchVector(models.Value(tag_names), config="english"),
            search_vector_english_description=SearchVector("description", config="english"),
        )

    def get_visualisation_links(self, request):
        @dataclass
        class _Link:
            name: str
            get_absolute_url: str
            modified_date: datetime

        links = []

        if self.visualisation_template:
            links.append(
                _Link(
                    name=self.visualisation_template.nice_name,
                    get_absolute_url=self.visualisation_template.get_absolute_url(),
                    modified_date=self.visualisation_template.modified_date,
                )
            )

        links += self.visualisationlink_set.all()

        return links

    def user_has_access(self, user):
        user_email_domain = user.email.split("@")[1]

        return (
            self.user_access_type in [UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN]
            or self.visualisationuserpermission_set.filter(user=user).exists()
            or user_email_domain in self.authorized_email_domains
        )

    def user_has_bookmarked(self, user):
        return self.visualisationbookmark_set.filter(user=user).exists()

    def toggle_bookmark(self, user):
        if self.user_has_bookmarked(user):
            self.visualisationbookmark_set.filter(user=user).delete()
        else:
            self.visualisationbookmark_set.create(user=user)

    def set_bookmark(self, user):
        if self.user_has_bookmarked(user):
            return
        self.visualisationbookmark_set.create(user=user)

    def unset_bookmark(self, user):
        if not self.user_has_bookmarked(user):
            return
        self.visualisationbookmark_set.filter(user=user).delete()

    def bookmark_count(self):
        return self.visualisationbookmark_set.count()

    def get_usage_history_url(self):
        return reverse("datasets:visualisation_usage_history", args=(self.id,))

    @staticmethod
    def get_type_display():
        return "Visualisation"

    def __str__(self):
        return self.name


class VisualisationUserPermission(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    visualisation = models.ForeignKey(VisualisationCatalogueItem, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_visualisationuserpermission"
        unique_together = ("user", "visualisation")


class VisualisationBookmark(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    visualisation = models.ForeignKey(VisualisationCatalogueItem, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_visualisationbookmark"
        unique_together = ("user", "visualisation")


class VisualisationLink(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visualisation_type = models.CharField(
        max_length=64,
        choices=(
            ("QUICKSIGHT", "AWS QuickSight"),
            ("SUPERSET", "Superset"),
        ),
        null=False,
        blank=False,
    )
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
        help_text="Used as the displayed text in the download link",
    )
    identifier = models.CharField(
        max_length=256,
        help_text="For QuickSight, the dashboard ID.",
    )
    visualisation_catalogue_item = models.ForeignKey(
        VisualisationCatalogueItem, on_delete=models.CASCADE
    )
    data_source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_visualisationlink"

    def get_absolute_url(self):
        return reverse("visualisations:link", kwargs={"link_id": self.id})


class VisualisationLinkSqlQuery(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_set_id = models.UUIDField()
    table_id = models.UUIDField()
    sql_query = models.TextField()
    is_latest = models.BooleanField()
    visualisation_link = models.ForeignKey(
        VisualisationLink, on_delete=models.CASCADE, related_name="sql_queries"
    )


class ToolQueryAuditLog(models.Model):
    # Note: Unique index on rolename, timestamp and md5 hash of query sql
    # created manually in migration 0065_add_audit_log_hashed_unique_index
    user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT)
    database = models.ForeignKey(Database, on_delete=models.PROTECT)
    rolename = models.CharField(max_length=64, null=False, blank=False)
    query_sql = models.TextField(null=False, blank=False)
    timestamp = models.DateTimeField(null=False, blank=False)
    connection_from = models.GenericIPAddressField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=("timestamp", "id")),
        ]


class ToolQueryAuditLogTable(models.Model):
    audit_log = models.ForeignKey(
        ToolQueryAuditLog, on_delete=models.CASCADE, related_name="tables"
    )
    schema = models.CharField(
        max_length=63,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
        default="public",
    )
    table = models.CharField(
        max_length=63,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )


class Notification(TimeStampedModel):
    changelog_id = models.IntegerField(unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.TextField()
    related_object = GenericForeignKey("content_type", "object_id")


class UserNotification(TimeStampedModel):
    notification = models.ForeignKey(Notification, on_delete=models.PROTECT)
    subscription = models.ForeignKey(DataSetSubscription, on_delete=models.PROTECT)
    email_id = models.UUIDField(null=True)

    class Meta:
        unique_together = ["notification", "subscription"]


class Pipeline(TimeStampedUserModel):
    table_name = models.CharField(max_length=256, unique=True)
    type = models.CharField(max_length=255, choices=PipelineType.choices)
    config = models.JSONField()

    class Meta:
        ordering = ("table_name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_table_name = self.table_name
        self._original_config = self.config

    def __str__(self):
        return self.dag_id

    @property
    def dag_id(self):
        return f"DerivedPipeline-{self.table_name}"

    def get_absolute_url(self):
        return reverse(f"pipelines:edit-{self.type}", args=(self.id,))

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.id is not None and (
            self._original_table_name != self.table_name or self._original_config != self.config
        ):
            PipelineVersion.objects.create(
                pipeline=self,
                table_name=self._original_table_name,
                config=self._original_config,
            )
            self._original_table_name = self.table_name
            self._original_config = self.config
        super().save(force_insert, force_update, using, update_fields)


class PipelineVersion(TimeStampedModel):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)
    table_name = models.CharField(max_length=256)
    config = models.JSONField()

    class Meta:
        get_latest_by = "created_date"
        ordering = ("-created_date",)

    def __str__(self):
        return f"{self.pipeline} backup {self.created_date}"


class PendingAuthorizedUsers(models.Model):
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    users = models.JSONField(null=True)
