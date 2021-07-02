import uuid
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from contextlib import closing
import csv
import io
from itertools import chain
import json
from typing import Set

import logging

import boto3
import psycopg2
from botocore.exceptions import ClientError
from csp.decorators import csp_update

from psycopg2 import sql
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates.general import ArrayAgg, BoolOr
from django.contrib.postgres.search import SearchRank
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import (
    Count,
    Exists,
    F,
    CharField,
    IntegerField,
    Q,
    Value,
    Case,
    When,
    BooleanField,
    OuterRef,
    QuerySet,
    Func,
)
from django.db.models.functions import TruncDay
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
)
from django.views.generic import DetailView, View
from waffle.mixins import WaffleFlagMixin

from dataworkspace import datasets_db
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.datasets.constants import (
    DataSetType,
    DataLinkType,
    UserAccessType,
)
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    database_dsn,
    streaming_query_response,
    table_data,
    view_exists,
    get_random_data_sample,
)
from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.forms import (
    DatasetSearchForm,
    EligibilityCriteriaForm,
    RelatedMastersSortForm,
    RelatedDataCutsSortForm,
    RelatedVisualisationsSortForm,
)
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataSet,
    DataSetVisualisation,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    SourceView,
    VisualisationCatalogueItem,
    SourceTable,
    ToolQueryAuditLogTable,
)
from dataworkspace.apps.datasets.utils import (
    build_filtered_dataset_query,
    dataset_type_to_manage_unpublished_permission_codename,
    find_dataset,
    find_dataset_or_visualisation,
    find_dataset_or_visualisation_for_bookmark,
    get_code_snippets_for_table,
    get_code_snippets_for_query,
    get_code_snippets_for_reference_table,
    get_detailed_changelog,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event


logger = logging.getLogger("app")


def get_datasets_data_for_user_matching_query(
    datasets: QuerySet,
    query,
    use=None,
    data_type=None,
    user=None,
    id_field="id",
):
    """
    Filters the dataset queryset for:
        1) visibility (whether the user can know if the dataset exists)
        2) matches the search terms

    Annotates the dataset queryset with:
        1) `has_access`, if the user can use the dataset's data.
    """
    is_reference_query = datasets.model is ReferenceDataset

    # Filter out datasets that the user is not allowed to even know about.
    visibility_filter = Q(published=True)

    if user:
        if is_reference_query:
            reference_type = DataSetType.REFERENCE
            reference_perm = dataset_type_to_manage_unpublished_permission_codename(reference_type)

            if user.has_perm(reference_perm):
                visibility_filter |= Q(published=False)

        if datasets.model is DataSet:
            master_type, datacut_type = (
                DataSetType.MASTER,
                DataSetType.DATACUT,
            )
            master_perm = dataset_type_to_manage_unpublished_permission_codename(master_type)
            datacut_perm = dataset_type_to_manage_unpublished_permission_codename(datacut_type)

            if user.has_perm(master_perm):
                visibility_filter |= Q(published=False, type=master_type)

            if user.has_perm(datacut_perm):
                visibility_filter |= Q(published=False, type=datacut_type)

    datasets = datasets.filter(visibility_filter)

    # Filter out datasets that don't match the search terms
    datasets = datasets.annotate(search_rank=SearchRank(F("search_vector"), query))

    if query:
        datasets = datasets.filter(search_vector=query)

    # Mark up whether the user can access the data in the dataset.
    access_filter = Q()
    bookmark_filter = Q(referencedatasetbookmark__user=user)

    if user and datasets.model is not ReferenceDataset:
        access_filter &= Q(
            user_access_type__in=[
                UserAccessType.REQUIRES_AUTHENTICATION,
                UserAccessType.OPEN,
            ]
        ) | Q(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            datasetuserpermission__user=user,
        )

        bookmark_filter = Q(datasetbookmark__user=user)

    datasets = datasets.annotate(
        _has_access=Case(
            When(access_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    datasets = datasets.annotate(
        _is_bookmarked=Case(
            When(bookmark_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if bookmark_filter
        else Value(True, BooleanField()),
    )

    # Pull in the source tag IDs for the dataset
    datasets = datasets.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )
    datasets = datasets.annotate(
        source_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    # Pull in the topic tag IDs for the dataset
    datasets = datasets.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )
    datasets = datasets.annotate(
        topic_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    # Define a `purpose` column denoting the dataset type.
    if is_reference_query:
        datasets = datasets.annotate(
            purpose=Value(DataSetType.DATACUT, IntegerField()),
            data_type=Value(DataSetType.REFERENCE, IntegerField()),
            is_open_data=Value(False, BooleanField()),
            has_visuals=Value(False, BooleanField()),
        )
    else:
        dataset_visual_filter = DataSetVisualisation.objects.filter(dataset_id=OuterRef("id"))
        datasets = datasets.annotate(
            purpose=F("type"),
            data_type=F("type"),
            is_open_data=Case(
                When(user_access_type=UserAccessType.OPEN, then=True),
                default=False,
                output_field=BooleanField(),
            ),
            has_visuals=Case(
                When(Exists(dataset_visual_filter), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )

    # We are joining on the user permissions table to determine `_has_access`` to the dataset, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    datasets = (
        datasets.values(
            id_field,
            "name",
            "slug",
            "short_description",
            "search_rank",
            "source_tag_names",
            "source_tag_ids",
            "topic_tag_names",
            "topic_tag_ids",
            "purpose",
            "data_type",
            "published",
            "published_at",
            "is_open_data",
            "has_visuals",
        )
        .annotate(has_access=BoolOr("_has_access"))
        .annotate(is_bookmarked=BoolOr("_is_bookmarked"))
    )

    return datasets.values(
        id_field,
        "name",
        "slug",
        "short_description",
        "search_rank",
        "source_tag_names",
        "source_tag_ids",
        "topic_tag_names",
        "topic_tag_ids",
        "purpose",
        "data_type",
        "published",
        "published_at",
        "is_open_data",
        "has_visuals",
        "has_access",
        "is_bookmarked",
    )


def get_visualisations_data_for_user_matching_query(visualisations: QuerySet, query, user=None):
    """
    Filters the visualisation queryset for:
        1) visibility (whether the user can know if the visualisation exists)
        2) matches the search terms

    Annotates the visualisation queryset with:
        1) `has_access`, if the user can use the visualisation.
    """
    # Filter out visualisations that the user is not allowed to even know about.
    if not (
        user
        and user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(DataSetType.VISUALISATION)
        )
    ):
        visualisations = visualisations.filter(published=True)

    # Filter out visualisations that don't match the search terms

    visualisations = visualisations.annotate(search_rank=SearchRank(F("search_vector"), query))

    if query:
        visualisations = visualisations.filter(search_vector=query)

    # Mark up whether the user can access the visualisation.
    if user:
        access_filter = (
            (
                Q(
                    user_access_type__in=[
                        UserAccessType.REQUIRES_AUTHENTICATION,
                        UserAccessType.OPEN,
                    ]
                )
            )
            & (
                Q(visualisationuserpermission__user=user)
                | Q(visualisationuserpermission__isnull=True)
            )
        ) | Q(
            user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
            visualisationuserpermission__user=user,
        )
    else:
        access_filter = Q()

    visualisations = visualisations.annotate(
        _has_access=Case(
            When(access_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    bookmark_filter = Q(visualisationbookmark__user=user)
    visualisations = visualisations.annotate(
        _is_bookmarked=Case(
            When(bookmark_filter, then=True),
            default=False,
            output_field=BooleanField(),
        )
        if bookmark_filter
        else Value(True, BooleanField()),
    )

    # Pull in the source tag IDs for the dataset
    visualisations = visualisations.annotate(
        source_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    visualisations = visualisations.annotate(
        source_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.SOURCE), distinct=True)
    )

    # Pull in the topic tag IDs for the dataset
    visualisations = visualisations.annotate(
        topic_tag_ids=ArrayAgg("tags", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    visualisations = visualisations.annotate(
        topic_tag_names=ArrayAgg("tags__name", filter=Q(tags__type=TagType.TOPIC), distinct=True)
    )

    visualisations = visualisations.annotate(
        # Define a `purpose` column denoting the dataset type
        purpose=Value(DataSetType.VISUALISATION, IntegerField()),
        data_type=Value(DataSetType.VISUALISATION, IntegerField()),
        is_open_data=Case(
            When(user_access_type=UserAccessType.OPEN, then=True),
            default=False,
            output_field=BooleanField(),
        ),
        has_visuals=Value(False, BooleanField()),
    )

    # We are joining on the user permissions table to determine `_has_access`` to the visualisation, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    visualisations = (
        visualisations.values(
            "id",
            "name",
            "slug",
            "short_description",
            "search_rank",
            "source_tag_names",
            "source_tag_ids",
            "topic_tag_names",
            "topic_tag_ids",
            "purpose",
            "data_type",
            "published",
            "published_at",
            "is_open_data",
            "has_visuals",
        )
        .annotate(has_access=BoolOr("_has_access"))
        .annotate(is_bookmarked=BoolOr("_is_bookmarked"))
    )

    return visualisations.values(
        "id",
        "name",
        "slug",
        "short_description",
        "search_rank",
        "source_tag_names",
        "source_tag_ids",
        "topic_tag_names",
        "topic_tag_ids",
        "purpose",
        "data_type",
        "published",
        "published_at",
        "is_open_data",
        "has_visuals",
        "has_access",
        "is_bookmarked",
    )


def _matches_filters(
    data,
    bookmark: bool,
    unpublished: bool,
    opendata: bool,
    withvisuals: bool,
    use: Set,
    data_type: Set,
    source_ids: Set,
    topic_ids: Set,
    user_accessible: bool = False,
    user_inaccessible: bool = False,
):
    return (
        (not bookmark or data["is_bookmarked"])
        and (unpublished or data["published"])
        and (not opendata or data["is_open_data"])
        and (not withvisuals or data["has_visuals"])
        and (not use or use == [None] or data["purpose"] in use)
        and (not data_type or data_type == [None] or data["data_type"] in data_type)
        and (not source_ids or source_ids.intersection(set(data["source_tag_ids"])))
        and (not topic_ids or topic_ids.intersection(set(data["topic_tag_ids"])))
        and (not user_accessible or data["has_access"])
        and (not user_inaccessible or not data["has_access"])
    )


def sorted_datasets_and_visualisations_matching_query_for_user(
    query, use, data_type, user, sort_by
):
    """
    Retrieves all master datasets, datacuts, reference datasets and visualisations (i.e. searchable items)
    and returns them, sorted by incoming sort field, default is desc(search_rank).
    """
    master_and_datacut_datasets = get_datasets_data_for_user_matching_query(
        DataSet.objects.live(), query, use, data_type, user=user, id_field="id"
    )

    reference_datasets = get_datasets_data_for_user_matching_query(
        ReferenceDataset.objects.live(),
        query,
        user=user,
        id_field="uuid",
    )

    visualisations = get_visualisations_data_for_user_matching_query(
        VisualisationCatalogueItem.objects.live(), query, user=user
    )

    # Combine all datasets and visualisations and order them.

    sort_fields = sort_by.split(",")

    all_datasets = (
        master_and_datacut_datasets.union(reference_datasets)
        .union(visualisations)
        .order_by(*sort_fields)
    )

    return all_datasets


def has_unpublished_dataset_access(user):
    access = user.is_superuser
    for dataset_type in DataSetType:
        access = access or user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(dataset_type.value)
        )

    return access


@require_GET
def find_datasets(request):
    form = DatasetSearchForm(request.GET)

    data_types = form.fields[
        "data_type"
    ].choices  # Cache these now, as we annotate them with result numbers later which we don't want here.

    if form.is_valid():
        query = form.cleaned_data.get("q")
        unpublished = "unpublished" in form.cleaned_data.get("admin_filters")
        open_data = "opendata" in form.cleaned_data.get("admin_filters")
        with_visuals = "withvisuals" in form.cleaned_data.get("admin_filters")
        use = set(form.cleaned_data.get("use"))
        data_type = set(form.cleaned_data.get("data_type", []))
        sort = form.cleaned_data.get("sort")
        source_ids = set(source.id for source in form.cleaned_data.get("source"))
        topic_ids = set(topic.id for topic in form.cleaned_data.get("topic"))
        bookmarked = form.cleaned_data.get("bookmarked")
        user_accessible = set(form.cleaned_data.get("user_access", [])) == {"yes"}
        user_inaccessible = set(form.cleaned_data.get("user_access", [])) == {"no"}
    else:
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    all_datasets_visible_to_user_matching_query = (
        sorted_datasets_and_visualisations_matching_query_for_user(
            query=query,
            use=use,
            data_type=data_type,
            user=request.user,
            sort_by=sort,
        )
    )

    # Filter out any records that don't match the selected filters. We do this in Python, not the DB, because we need
    # to run varied aggregations on the datasets in order to count how many records will be available if users apply
    # additional filters and this was difficult to do in the DB. This process will slowly degrade over time but should
    # be sufficient while the number of datasets is relatively low (hundreds/thousands).
    datasets_matching_query_and_filters = list(
        filter(
            lambda d: _matches_filters(
                d,
                bookmarked,
                bool(unpublished),
                bool(open_data),
                bool(with_visuals),
                use,
                data_type,
                source_ids,
                topic_ids,
                user_accessible,
                user_inaccessible,
            ),
            all_datasets_visible_to_user_matching_query,
        )
    )

    # Calculate counts of datasets that will match if users apply additional filters and apply these to the form
    # labels.
    form.annotate_and_update_filters(
        all_datasets_visible_to_user_matching_query,
        matcher=_matches_filters,
        number_of_matches=len(datasets_matching_query_and_filters),
    )

    paginator = Paginator(
        datasets_matching_query_and_filters,
        settings.SEARCH_RESULTS_DATASETS_PER_PAGE,
    )

    data_types.append((DataSetType.VISUALISATION, "Visualisation"))
    return render(
        request,
        "datasets/index.html",
        {
            "form": form,
            "query": query,
            "datasets": paginator.get_page(request.GET.get("page")),
            "data_type": dict(data_types),
            "show_admin_filters": has_unpublished_dataset_access(request.user),
            "DATASET_FINDER_FLAG": settings.DATASET_FINDER_ADMIN_ONLY_FLAG,
        },
    )


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def _is_visualisation(self):
        return isinstance(self.object, VisualisationCatalogueItem)

    def get_object(self, queryset=None):
        dataset_uuid = self.kwargs["dataset_uuid"]
        dataset = None
        try:
            dataset = ReferenceDataset.objects.live().get(uuid=dataset_uuid)
        except ReferenceDataset.DoesNotExist:
            try:
                dataset = DataSet.objects.live().get(id=dataset_uuid)
            except DataSet.DoesNotExist:
                try:
                    dataset = VisualisationCatalogueItem.objects.live().get(id=dataset_uuid)
                except VisualisationCatalogueItem.DoesNotExist:
                    pass

        if dataset:
            perm_codename = dataset_type_to_manage_unpublished_permission_codename(dataset.type)

            if not dataset.published and not self.request.user.has_perm(perm_codename):
                dataset = None

        if not dataset:
            raise Http404("No dataset matches the given query.")

        return dataset

    @csp_update(frame_src=settings.QUICKSIGHT_DASHBOARD_HOST)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def _get_source_text(self, model):
        source_text = ",".join(
            sorted({t.name for t in self.object.tags.filter(type=TagType.SOURCE)})
        )
        return source_text

    def _get_user_tools_access(self) -> bool:
        user_has_tools_access = self.request.user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        return user_has_tools_access

    def _get_context_data_for_master_dataset(self, ctx, **kwargs):
        source_tables = sorted(self.object.sourcetable_set.all(), key=lambda x: x.name)

        MasterDatasetInfo = namedtuple(
            "MasterDatasetInfo", ("source_table", "code_snippets", "columns")
        )
        master_datasets_info = [
            MasterDatasetInfo(
                source_table=source_table,
                code_snippets=get_code_snippets_for_table(source_table),
                columns=datasets_db.get_columns(
                    source_table.database.memorable_name,
                    schema=source_table.schema,
                    table=source_table.table,
                    include_types=True,
                ),
            )
            for source_table in sorted(source_tables, key=lambda x: x.name)
        ]

        summarised_update_frequency = ",".join(
            sorted({t.get_frequency_display() for t in source_tables})
        )

        subscription = self.object.subscriptions.filter(user=self.request.user)

        ctx.update(
            {
                "summarised_update_frequency": summarised_update_frequency,
                "source_text": self._get_source_text(self.object),
                "has_access": self.object.user_has_access(self.request.user),
                "has_tools_access": self._get_user_tools_access(),
                "is_bookmarked": self.object.user_has_bookmarked(self.request.user),
                "master_datasets_info": master_datasets_info,
                "source_table_type": DataLinkType.SOURCE_TABLE,
                "related_data": self.object.related_datasets(),
                "related_visualisations": self.object.related_visualisations.filter(
                    published=True
                ),
                "subscription": {
                    "current_user_is_subscribed": subscription.exists()
                    and subscription.first().is_active(),
                    "details": subscription.first(),
                },
            }
        )
        return ctx

    def _get_context_data_for_datacut_dataset(self, ctx, **kwargs):
        custom_queries = self.object.customdatasetquery_set.all().prefetch_related("tables")
        datacut_links = sorted(
            chain(
                self.object.sourcetable_set.all(),
                self.object.sourcelink_set.all(),
                custom_queries,
            ),
            key=lambda x: x.name,
        )

        summarised_update_frequency = ",".join(
            sorted({t.get_frequency_display() for t in datacut_links})
        )

        DatacutLinkInfo = namedtuple(
            "DatacutLinkInfo",
            ("datacut_link", "can_show_link", "code_snippets", "columns"),
        )
        datacut_links_info = [
            DatacutLinkInfo(
                datacut_link=datacut_link,
                can_show_link=datacut_link.can_show_link_for_user(self.request.user),
                code_snippets=(
                    get_code_snippets_for_query(datacut_link.query)
                    if hasattr(datacut_link, "query")
                    else None
                ),
                columns=(
                    datasets_db.get_columns(
                        database_name=datacut_link.database.memorable_name,
                        query=datacut_link.query,
                        include_types=True,
                    )
                    if hasattr(datacut_link, "query")
                    else None
                ),
            )
            for datacut_link in datacut_links
        ]

        subscription = self.object.subscriptions.filter(user=self.request.user)

        ctx.update(
            {
                "has_access": self.object.user_has_access(self.request.user),
                "is_bookmarked": self.object.user_has_bookmarked(self.request.user),
                "datacut_links_info": datacut_links_info,
                "data_hosted_externally": any(
                    not source_link.url.startswith("s3://")
                    for source_link in self.object.sourcelink_set.all()
                ),
                "custom_dataset_query_type": DataLinkType.CUSTOM_QUERY,
                "related_data": self.object.related_datasets(),
                "related_visualisations": self.object.related_visualisations.filter(
                    published=True
                ),
                "summarised_update_frequency": summarised_update_frequency,
                "source_text": self._get_source_text(self.object),
                "subscription": {
                    "current_user_is_subscribed": subscription.exists()
                    and subscription.first().is_active(),
                    "details": subscription.first(),
                },
            }
        )
        return ctx

    def _get_context_data_for_reference_dataset(self, ctx, **kwargs):
        records = self.object.get_records()
        total_record_count = records.count()
        preview_limit = self.get_preview_limit(total_record_count)
        records = records[:preview_limit]
        code_snippets = get_code_snippets_for_reference_table(self.object.table_name)
        columns = None
        if self.object.external_database:
            columns = datasets_db.get_columns(
                self.object.external_database.memorable_name,
                schema="public",
                table=self.object.table_name,
                include_types=True,
            )

        subscription = self.object.subscriptions.filter(user=self.request.user)

        ctx.update(
            {
                "preview_limit": preview_limit,
                "record_count": total_record_count,
                "records": records,
                "is_bookmarked": self.object.user_has_bookmarked(self.request.user),
                "DATA_GRID_REFERENCE_DATASET_FLAG": settings.DATA_GRID_REFERENCE_DATASET_FLAG,
                "code_snippets": code_snippets,
                "columns": columns,
                "subscription": {
                    "current_user_is_subscribed": subscription.exists()
                    and subscription.first().is_active(),
                    "details": subscription.first(),
                },
            }
        )
        return ctx

    def _get_context_data_for_visualisation(self, ctx, **kwargs):
        ctx.update(
            {
                "has_access": self.object.user_has_access(self.request.user),
                "is_bookmarked": self.object.user_has_bookmarked(self.request.user),
                "visualisation_links": self.object.get_visualisation_links(self.request),
                "summarised_update_frequency": "N/A",
                "source_text": self._get_source_text(self.object),
            }
        )
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx["model"] = self.object
        ctx["DATA_CUT_ENHANCED_PREVIEW_FLAG"] = settings.DATA_CUT_ENHANCED_PREVIEW_FLAG
        ctx["DATASET_CHANGELOG_PAGE_FLAG"] = settings.DATASET_CHANGELOG_PAGE_FLAG

        if self._is_reference_dataset():
            return self._get_context_data_for_reference_dataset(ctx, **kwargs)

        elif self._is_visualisation():
            return self._get_context_data_for_visualisation(ctx, **kwargs)

        elif self.object.type == DataSetType.MASTER:
            return self._get_context_data_for_master_dataset(ctx, **kwargs)

        elif self.object.type == DataSetType.DATACUT:
            return self._get_context_data_for_datacut_dataset(ctx, **kwargs)

        raise ValueError(f"Unknown dataset/type for {self.__class__.__name__}: {self.object}")

    def get_template_names(self):

        if self._is_reference_dataset():
            return ["datasets/referencedataset_detail.html"]
        elif self.object.type == DataSetType.MASTER:
            return ["datasets/master_dataset.html"]
        elif self.object.type == DataSetType.DATACUT:
            return ["datasets/data_cut_dataset.html"]
        elif self._is_visualisation():
            return ["datasets/visualisation_catalogue_item.html"]

        raise RuntimeError(f"Unknown template for {self}")

    def get_preview_limit(self, record_count):
        return min([record_count, settings.REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS])


@require_http_methods(["GET", "POST"])
def eligibility_criteria_view(request, dataset_uuid):
    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    if request.method == "POST":
        form = EligibilityCriteriaForm(request.POST)
        if form.is_valid():
            access_request_id = form.cleaned_data.get("access_request")
            if form.cleaned_data["meet_criteria"]:
                url = reverse("request_access:dataset", args=[dataset_uuid])
                if access_request_id:
                    url = reverse(
                        "request_access:dataset-request-update",
                        args=[access_request_id],
                    )
            else:
                url = reverse("datasets:eligibility_criteria_not_met", args=[dataset_uuid])

            return HttpResponseRedirect(url)

    return render(
        request,
        "eligibility_criteria.html",
        {"dataset": dataset, "access_request": request.GET.get("access_request")},
    )


@require_GET
def eligibility_criteria_not_met_view(request, dataset_uuid):
    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    return render(
        request,
        "eligibility_criteria_not_met.html",
        {
            "dataset": dataset,
            "is_visualisation": isinstance(dataset, VisualisationCatalogueItem),
        },
    )


@require_GET
def toggle_bookmark(request, dataset_uuid):
    dataset = find_dataset_or_visualisation_for_bookmark(dataset_uuid)
    dataset.toggle_bookmark(request.user)

    return HttpResponseRedirect(dataset.get_absolute_url())


class ReferenceDatasetDownloadView(DetailView):
    model = ReferenceDataset

    def get_object(self, queryset=None):
        return get_object_or_404(
            ReferenceDataset.objects.live(),
            uuid=self.kwargs.get("dataset_uuid"),
            **{"published": True} if not self.request.user.is_superuser else {},
        )

    def get(self, request, *args, **kwargs):
        dl_format = self.kwargs.get("format")
        if dl_format not in ["json", "csv"]:
            raise Http404
        ref_dataset = self.get_object()
        records = []
        for record in ref_dataset.get_records():
            record_data = {}
            for field in ref_dataset.fields.all():
                if field.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    relationship = getattr(record, field.relationship_name)
                    record_data[field.name] = (
                        getattr(
                            relationship,
                            field.linked_reference_dataset_field.column_name,
                        )
                        if relationship
                        else None
                    )
                else:
                    record_data[field.name] = getattr(record, field.column_name)
            records.append(record_data)

        response = HttpResponse()
        response["Content-Disposition"] = "attachment; filename={}-{}.{}".format(
            ref_dataset.slug, ref_dataset.published_version, dl_format
        )

        log_event(
            request.user,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
            ref_dataset,
            extra={
                "path": request.get_full_path(),
                "reference_dataset_version": ref_dataset.published_version,
                "download_format": dl_format,
            },
        )
        ref_dataset.number_of_downloads = F("number_of_downloads") + 1
        ref_dataset.save(update_fields=["number_of_downloads"])

        if dl_format == "json":
            response["Content-Type"] = "application/json"
            response.write(json.dumps(list(records), cls=DjangoJSONEncoder))
        else:
            response["Content-Type"] = "text/csv"
            with closing(io.StringIO()) as outfile:
                writer = csv.DictWriter(
                    outfile,
                    fieldnames=ref_dataset.export_field_names,
                    quoting=csv.QUOTE_NONNUMERIC,
                )
                writer.writeheader()
                writer.writerows(records)
                response.write(outfile.getvalue())  # pylint: disable=no-member
        return response


class SourceLinkDownloadView(DetailView):
    model = SourceLink

    def get(self, request, *args, **kwargs):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), request.user)

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        source_link = get_object_or_404(
            SourceLink, id=self.kwargs.get("source_link_id"), dataset=dataset
        )

        log_event(
            request.user,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
            source_link.dataset,
            extra={
                "path": request.get_full_path(),
                **serializers.serialize("python", [source_link])[0],
            },
        )
        dataset.number_of_downloads = F("number_of_downloads") + 1
        dataset.save(update_fields=["number_of_downloads"])

        if source_link.link_type == source_link.TYPE_EXTERNAL:
            return HttpResponseRedirect(source_link.url)

        client = boto3.client("s3")
        try:
            file_object = client.get_object(
                Bucket=settings.AWS_UPLOADS_BUCKET, Key=source_link.url
            )
        except ClientError as ex:
            try:
                return HttpResponse(status=ex.response["ResponseMetadata"]["HTTPStatusCode"])
            except KeyError:
                return HttpResponseServerError()

        response = StreamingHttpResponseWithoutDjangoDbConnection(
            file_object["Body"].iter_chunks(chunk_size=65536),
            content_type=file_object["ContentType"],
        )
        response["Content-Disposition"] = f'attachment; filename="{source_link.get_filename()}"'
        response["Content-Length"] = file_object["ContentLength"]

        return response


class SourceDownloadMixin:
    pk_url_kwarg = "source_id"
    event_log_type = None

    @staticmethod
    def db_object_exists(db_object):
        raise NotImplementedError()

    def get_table_data(self, db_object):
        raise NotImplementedError()

    def get(self, request, *_, **__):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), request.user)
        db_object = get_object_or_404(self.model, id=self.kwargs.get("source_id"), dataset=dataset)

        if not db_object.dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        if not self.db_object_exists(db_object):
            return HttpResponseNotFound()

        log_event(
            request.user,
            self.event_log_type,
            db_object.dataset,
            extra={
                "path": request.get_full_path(),
                **serializers.serialize("python", [db_object])[0],
            },
        )
        dataset.number_of_downloads = F("number_of_downloads") + 1
        dataset.save(update_fields=["number_of_downloads"])
        return self.get_table_data(db_object)


class SourceViewDownloadView(SourceDownloadMixin, DetailView):
    model = SourceView
    event_log_type = EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD

    @staticmethod
    def db_object_exists(db_object):
        return view_exists(db_object.database.memorable_name, db_object.schema, db_object.view)

    def get_table_data(self, db_object):
        return table_data(
            self.request.user.email,
            db_object.database.memorable_name,
            db_object.schema,
            db_object.view,
            db_object.get_filename(),
        )


class CustomDatasetQueryDownloadView(DetailView):
    model = CustomDatasetQuery

    def get(self, request, *args, **kwargs):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), request.user)

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        query = get_object_or_404(self.model, id=self.kwargs.get("query_id"), dataset=dataset)

        if not query.reviewed and not request.user.is_superuser:
            return HttpResponseForbidden()

        log_event(
            request.user,
            EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
            query.dataset,
            extra={
                "path": request.get_full_path(),
                **serializers.serialize("python", [query])[0],
            },
        )
        dataset.number_of_downloads = F("number_of_downloads") + 1
        dataset.save(update_fields=["number_of_downloads"])

        filtered_query = sql.SQL(query.query)
        columns = request.GET.getlist("columns")

        if columns:
            trimmed_query = query.query.rstrip().rstrip(";")

            filtered_query = sql.SQL("SELECT {fields} from ({query}) as data;").format(
                fields=sql.SQL(",").join([sql.Identifier(column) for column in columns]),
                query=sql.SQL(trimmed_query),
            )

        return streaming_query_response(
            request.user.email,
            query.database.memorable_name,
            filtered_query,
            query.get_filename(),
            cursor_name=f"custom_query--{query.id}",
        )


class DatasetPreviewView(DetailView, metaclass=ABCMeta):
    @property
    @abstractmethod
    def model(self):
        pass

    @abstractmethod
    def get_preview_data(self, dataset):
        pass

    def get(self, request, *args, **kwargs):
        user = self.request.user
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), user)

        if not dataset.user_has_access(user):
            return HttpResponseForbidden()

        source_object, columns, query = self.get_preview_data(dataset)

        records = []
        sample_size = settings.DATASET_PREVIEW_NUM_OF_ROWS
        if columns:
            rows = get_random_data_sample(
                source_object.database.memorable_name,
                sql.SQL(query),
                sample_size,
            )
            for row in rows:
                record_data = {}
                for i, column in enumerate(columns):
                    record_data[column] = row[i]
                records.append(record_data)

        can_download = source_object.can_show_link_for_user(user)

        return render(
            request,
            "datasets/dataset_preview.html",
            {
                "dataset": dataset,
                "source_object": source_object,
                "fields": columns,
                "records": records,
                "preview_limit": sample_size,
                "record_count": len(records),
                "fixed_table_height_limit": 10,
                "truncate_limit": 100,
                "can_download": can_download,
                "type": source_object.type,
            },
        )


class SourceTablePreviewView(DatasetPreviewView):
    model = SourceTable

    def get_preview_data(self, dataset):
        source_table_object = get_object_or_404(
            self.model, id=self.kwargs.get("table_uuid"), dataset=dataset
        )
        database_name = source_table_object.database.memorable_name
        table_name = source_table_object.table
        schema_name = source_table_object.schema
        columns = datasets_db.get_columns(database_name, schema=schema_name, table=table_name)
        preview_query = f"""
            select * from "{schema_name}"."{table_name}"
        """
        return source_table_object, columns, preview_query


class CustomDatasetQueryPreviewView(DatasetPreviewView):
    model = CustomDatasetQuery

    def get_preview_data(self, dataset):
        query_object = get_object_or_404(
            self.model, id=self.kwargs.get("query_id"), dataset=dataset
        )

        if not query_object.reviewed and not self.request.user.is_superuser:
            raise PermissionDenied()

        database_name = query_object.database.memorable_name
        columns = datasets_db.get_columns(database_name, query=query_object.query)
        preview_query = query_object.query

        return query_object, columns, preview_query


class SourceTableColumnDetails(View):
    def get(self, request, dataset_uuid, table_uuid):
        try:
            dataset = DataSet.objects.get(id=dataset_uuid, type=DataSetType.MASTER)
            source_table = SourceTable.objects.get(id=table_uuid, dataset__id=dataset_uuid)
        except (DataSet.DoesNotExist, SourceTable.DoesNotExist):
            return HttpResponse(status=404)

        columns = datasets_db.get_columns(
            source_table.database.memorable_name,
            schema=source_table.schema,
            table=source_table.table,
            include_types=True,
        )
        return render(
            request,
            "datasets/source_table_column_details.html",
            context={
                "dataset": dataset,
                "source_table": source_table,
                "columns": columns,
            },
        )


class ReferenceDatasetColumnDetails(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(
            ReferenceDataset.objects.live(),
            uuid=dataset_uuid,
            **{"published": True} if not self.request.user.is_superuser else {},
        )

        columns = datasets_db.get_columns(
            dataset.external_database.memorable_name,
            schema="public",
            table=dataset.table_name,
            include_types=True,
        )
        return render(
            request,
            "datasets/referencedataset_column_details.html",
            context={"dataset": dataset, "columns": columns},
        )


class ReferenceDatasetGridView(View):
    def get(self, request, dataset_uuid):
        dataset = get_object_or_404(
            ReferenceDataset.objects.live(),
            uuid=dataset_uuid,
            **{"published": True} if not self.request.user.is_superuser else {},
        )

        return render(
            request,
            "datasets/reference_dataset_grid.html",
            context={"model": dataset},
        )


class RelatedDataView(View):
    def get(self, request, dataset_uuid):
        try:
            dataset = DataSet.objects.get(id=dataset_uuid)
        except DataSet.DoesNotExist:
            return HttpResponse(status=404)

        if dataset.type == DataSetType.DATACUT:
            form = RelatedMastersSortForm(request.GET)

        elif dataset.type == DataSetType.MASTER:
            form = RelatedDataCutsSortForm(request.GET)

        else:
            return HttpResponse(status=404)

        if form.is_valid():
            related_datasets = dataset.related_datasets(
                order=form.cleaned_data.get("sort") or form.fields["sort"].initial
            )

            return render(
                request,
                "datasets/related_data.html",
                context={
                    "dataset": dataset,
                    "related_data": related_datasets,
                    "form": form,
                },
            )

        return HttpResponse(status=500)


class RelatedVisualisationsView(View):
    def get(self, request, dataset_uuid):
        try:
            dataset = DataSet.objects.get(id=dataset_uuid)
        except DataSet.DoesNotExist:
            return HttpResponse(status=404)

        form = RelatedVisualisationsSortForm(request.GET)

        if form.is_valid():
            related_visualisations = dataset.related_visualisations.order_by(
                form.cleaned_data.get("sort") or form.fields["sort"].initial
            )

            return render(
                request,
                "datasets/related_visualisations.html",
                context={
                    "dataset": dataset,
                    "related_visualisations": related_visualisations,
                    "form": form,
                },
            )

        return HttpResponse(status=500)


class DataCutPreviewView(WaffleFlagMixin, DetailView):
    waffle_flag = settings.DATA_CUT_ENHANCED_PREVIEW_FLAG
    template_name = "datasets/data_cut_preview.html"

    def dispatch(self, request, *args, **kwargs):
        if not self.get_object().dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(self.kwargs["model_class"], pk=self.kwargs["object_id"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        model = self.get_object()
        ctx.update(
            {
                "can_download": model.can_show_link_for_user(self.request.user),
                "form_action": model.get_absolute_url(),
                "can_filter_columns": model.show_column_filter(),
                "truncate_limit": 100,
                "fixed_table_height_limit": 10,
            }
        )
        if model.user_can_preview(self.request.user):
            columns, records = model.get_preview_data()
            ctx.update(
                {
                    "columns": columns,
                    "records": records,
                    "preview_limit": min(
                        [len(records), settings.REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS]
                    ),
                }
            )
        return ctx


class DatasetUsageHistoryView(View):
    def get(self, request, dataset_uuid, **kwargs):
        model_class = kwargs["model_class"]
        try:
            dataset = model_class.objects.get(id=dataset_uuid)
        except model_class.DoesNotExist:
            return HttpResponse(status=404)

        if dataset.type == DataSetType.MASTER:
            tables = list(dataset.sourcetable_set.values_list("table", flat=True))
            return render(
                request,
                "datasets/dataset_usage_history.html",
                context={
                    "dataset": dataset,
                    "event_description": "Queried",
                    "rows": ToolQueryAuditLogTable.objects.filter(table__in=tables)
                    .annotate(day=TruncDay("audit_log__timestamp"))
                    .annotate(email=F("audit_log__user__email"))
                    .annotate(object=F("table"))
                    .order_by("-day")
                    .values("day", "email", "object")
                    .annotate(count=Count("id"))[:100],
                },
            )

        return render(
            request,
            "datasets/dataset_usage_history.html",
            context={
                "dataset": dataset,
                "event_description": "Viewed"
                if dataset.type == DataSetType.VISUALISATION
                else "Downloaded",
                "rows": dataset.events.filter(
                    event_type__in=[
                        EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
                        EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
                        EventLog.TYPE_VIEW_VISUALISATION_TEMPLATE,
                        EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
                        EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
                    ]
                )
                .annotate(day=TruncDay("timestamp"))
                .annotate(email=F("user__email"))
                .annotate(
                    object=Func(
                        F("extra"),
                        Value("fields"),
                        Value("name"),
                        function="jsonb_extract_path_text",
                        output_field=CharField(),
                    ),
                )
                .order_by("-day")
                .values("day", "email", "object")
                .annotate(count=Count("id"))[:100],
            },
        )


class DataCutSourceDetailView(DetailView):
    template_name = "datasets/data_cut_source_detail.html"

    def _user_can_access(self):
        source = self.get_object()
        return source.dataset.user_has_access(self.request.user) and source.data_grid_enabled

    def dispatch(self, request, *args, **kwargs):
        if not self._user_can_access():
            dataset_uuid = self.kwargs.get("dataset_uuid")
            dataset = find_dataset(dataset_uuid, self.request.user)

            return HttpResponseRedirect(dataset.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset__id=self.kwargs.get("dataset_uuid"),
            pk=self.kwargs["object_id"],
            **{"dataset__published": True} if not self.request.user.is_superuser else {},
        )


class DataGridDataView(DetailView):
    def _user_can_access(self):
        source = self.get_object()
        return source.dataset.user_has_access(self.request.user) and source.data_grid_enabled

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset__id=self.kwargs.get("dataset_uuid"),
            pk=self.kwargs["object_id"],
            **{"dataset__published": True} if not self.request.user.is_superuser else {},
        )

    def dispatch(self, request, *args, **kwargs):
        if not self._user_can_access():
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _get_rows(source, query, query_params):
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[source.database.memorable_name])
        ) as connection:
            with connection.cursor(
                name="data-grid-data",
                cursor_factory=psycopg2.extras.RealDictCursor,
            ) as cursor:
                cursor.execute(query, query_params)
                return cursor.fetchall()

    def post(self, request, *args, **kwargs):
        source = self.get_object()

        if request.GET.get("download"):
            if not source.data_grid_download_enabled:
                return JsonResponse({}, status=403)

            filters = {}
            for filter_data in [json.loads(x) for x in request.POST.getlist("filters")]:
                filters.update(filter_data)
            column_config = [
                x
                for x in source.get_column_config()
                if x["field"] in request.POST.getlist("columns", [])
            ]
            if not column_config:
                return JsonResponse({}, status=400)

            post_data = {
                "filters": filters,
                "limit": source.data_grid_download_limit,
                "sortDir": request.POST.get("sortDir", "ASC"),
                "sortField": request.POST.get("sortField", column_config[0]["field"]),
            }
        else:
            post_data = json.loads(request.body.decode("utf-8"))
            post_data["limit"] = min(post_data.get("limit", 100), 100)
            column_config = source.get_column_config()

        original_query = source.get_data_grid_query()
        query, params = build_filtered_dataset_query(
            original_query,
            column_config,
            post_data,
        )

        if request.GET.get("download"):
            correlation_id = {"correlation_id": str(uuid.uuid4())}

            log_event(
                request.user,
                EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
                source,
                extra=correlation_id,
            )

            def write_metrics_to_eventlog(log_data):
                logger.debug("write_metrics_to_eventlog %s", log_data)

                log_data.update(correlation_id)
                log_event(
                    request.user,
                    EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE,
                    source,
                    extra=log_data,
                )

            return streaming_query_response(
                request.user.email,
                source.database.memorable_name,
                query,
                request.POST.get("export_file_name", f"custom-{source.dataset.slug}-export.csv"),
                params,
                original_query,
                write_metrics_to_eventlog,
                cursor_name=f'data-grid--{self.kwargs["model_class"].__name__}--{source.id}',
            )

        records = self._get_rows(source, query, params)
        return JsonResponse({"records": records})


class DatasetVisualisationPreview(View):
    def _get_vega_definition(self, visualisation):
        vega_definition = json.loads(visualisation.vega_definition_json)

        if visualisation.query:
            with psycopg2.connect(
                database_dsn(settings.DATABASES_DATA[visualisation.database.memorable_name])
            ) as connection:
                with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(visualisation.query)
                    data = cursor.fetchall()
            try:
                # vega-lite, 'data' is a dictionary
                vega_definition["data"]["values"] = data
            except TypeError:
                # vega, 'data' is a list, and we support setting the query
                # results as the first item
                vega_definition["data"][0]["values"] = data

        return vega_definition

    def get(self, request, dataset_uuid, object_id, **kwargs):
        model_class = kwargs["model_class"]
        try:
            dataset = model_class.objects.get(id=dataset_uuid)
        except model_class.DoesNotExist:
            return HttpResponse(status=404)

        if not dataset.user_has_access(request.user):
            return HttpResponseForbidden()

        visualisation = dataset.visualisations.get(id=object_id)
        vega_definition = self._get_vega_definition(visualisation)

        return JsonResponse(vega_definition)


class DatasetVisualisationView(View):
    def get(self, request, dataset_uuid, object_id, **kwargs):
        model_class = kwargs["model_class"]
        try:
            dataset = model_class.objects.get(id=dataset_uuid)
        except model_class.DoesNotExist:
            return HttpResponse(status=404)

        if not dataset.user_has_access(request.user):
            return HttpResponseForbidden()

        visualisation = dataset.visualisations.live().get(id=object_id)

        return render(
            request,
            "datasets/visualisation.html",
            context={"dataset_uuid": dataset_uuid, "visualisation": visualisation},
        )


class CustomQueryColumnDetails(View):
    def get(self, request, dataset_uuid, query_id):
        try:
            dataset = DataSet.objects.get(id=dataset_uuid, type=DataSetType.DATACUT)
            query = CustomDatasetQuery.objects.get(id=query_id, dataset__id=dataset_uuid)
        except (DataSet.DoesNotExist, CustomDatasetQuery.DoesNotExist):
            return HttpResponse(status=404)

        return render(
            request,
            "datasets/data_cut_column_details.html",
            context={
                "dataset": dataset,
                "query": query,
                "columns": datasets_db.get_columns(
                    query.database.memorable_name, query=query.query, include_types=True
                ),
            },
        )


class SourceChangelogView(WaffleFlagMixin, DetailView):
    waffle_flag = settings.DATASET_CHANGELOG_PAGE_FLAG
    template_name = "datasets/source_changelog.html"
    context_object_name = "source"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["changelog"] = get_detailed_changelog(self.get_object())
        return ctx

    def get_object(self, queryset=None):
        if self.kwargs["model_class"] == ReferenceDataset:
            return get_object_or_404(
                self.kwargs["model_class"],
                uuid=self.kwargs.get("dataset_uuid"),
                **{"published": True} if not self.request.user.is_superuser else {},
            )
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset__id=self.kwargs.get("dataset_uuid"),
            pk=self.kwargs["source_id"],
            **{"dataset__published": True} if not self.request.user.is_superuser else {},
        )


class DatasetChartView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_PUBLISH_CHARTS_FLAG

    def get_object(self):
        dataset = get_object_or_404(
            self.kwargs["model_class"],
            id=self.kwargs["dataset_uuid"],
            **{"published": True} if not self.request.user.is_superuser else {},
        )
        return dataset.charts.get(id=self.kwargs["object_id"])

    @csp_update(SCRIPT_SRC=["'unsafe-eval'", "blob:"])
    def get(self, request, **kwargs):
        chart = self.get_object()
        if not chart.dataset.user_has_access(request.user):
            return HttpResponseForbidden()
        return render(
            request,
            "datasets/chart.html",
            context={
                "chart": chart,
            },
        )


class DatasetChartDataView(DatasetChartView):
    waffle_flag = settings.CHART_BUILDER_PUBLISH_CHARTS_FLAG

    def get(self, request, **kwargs):
        dataset_chart = self.get_object()
        if not dataset_chart.dataset.user_has_access(request.user):
            return HttpResponseForbidden()
        chart = dataset_chart.chart
        return JsonResponse(
            {
                "total_rows": chart.query_log.rows,
                "duration": chart.query_log.duration,
                "data": chart.get_table_data(chart.get_required_columns()),
            }
        )
