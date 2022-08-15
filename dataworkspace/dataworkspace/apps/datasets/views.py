import json
import logging
import uuid
from abc import ABCMeta, abstractmethod
from collections import defaultdict, namedtuple
from itertools import chain
from typing import Set

import psycopg2
from botocore.exceptions import ClientError
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connections, ProgrammingError
from django.db.models import (
    Count,
    F,
    CharField,
    Value,
    Func,
    Q,
    Prefetch,
)
from django.db.models.functions import TruncDay
from django.forms.models import model_to_dict
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
    require_POST,
    require_http_methods,
)
from django.views.generic import DetailView, FormView, TemplateView, UpdateView, View
from psycopg2 import sql
from waffle.mixins import WaffleFlagMixin

from dataworkspace import datasets_db
from dataworkspace.apps.api_v1.core.views import invalidate_superset_user_cached_credentials
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.charts.models import ChartBuilderChart
from dataworkspace.apps.core.charts.tasks import run_chart_builder_query

from dataworkspace.apps.core.errors import DatasetPermissionDenied, DatasetPreviewDisabledError
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    database_dsn,
    streaming_query_response,
    table_data,
    view_exists,
    get_random_data_sample,
)
from dataworkspace.apps.core.models import (
    Database,
)
from dataworkspace.apps.datasets.constants import (
    DataSetType,
    DataLinkType,
    AggregationType,
)
from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.forms import (
    ChartAggregateForm,
    ChartSourceSelectForm,
    DatasetEditForm,
    DatasetSearchForm,
    EligibilityCriteriaForm,
    RelatedMastersSortForm,
    RelatedDataCutsSortForm,
    RelatedVisualisationsSortForm,
    UserSearchForm,
    VisualisationCatalogueItemEditForm,
)
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DataSet,
    DataSetUserPermission,
    PendingAuthorizedUsers,
    MasterDataset,
    ReferenceDataset,
    SourceLink,
    SourceView,
    VisualisationCatalogueItem,
    SourceTable,
    ToolQueryAuditLogTable,
    Tag,
    VisualisationUserPermission,
)
from dataworkspace.apps.datasets.permissions.utils import (
    process_dataset_authorized_users_change,
    process_visualisation_catalogue_item_authorized_users_change,
)
from dataworkspace.apps.datasets.search import search_for_datasets
from dataworkspace.apps.datasets.utils import (
    build_filtered_dataset_query,
    dataset_type_to_manage_unpublished_permission_codename,
    find_dataset,
    get_code_snippets_for_table,
    get_code_snippets_for_query,
    get_code_snippets_for_reference_table,
    get_detailed_changelog,
    get_tools_links_for_user,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event, log_permission_change
from dataworkspace.apps.explorer.utils import invalidate_data_explorer_user_cached_credentials

logger = logging.getLogger("app")


def _matches_filters(
    data,
    unpublished: bool,
    opendata: bool,
    withvisuals: bool,
    use: Set,
    data_type: Set,
    source_ids: Set,
    topic_ids: Set,
    user_accessible: bool = False,
    user_inaccessible: bool = False,
    selected_user_datasets: Set = None,
):
    users_datasets = set()
    if data["is_bookmarked"]:
        users_datasets.add("bookmarked")
    if data["is_subscribed"]:
        users_datasets.add("subscribed")
    if data["is_owner"]:
        users_datasets.add("owned")

    return (
        (
            not selected_user_datasets
            or selected_user_datasets == [None]
            or set(selected_user_datasets).intersection(users_datasets)
        )
        and (unpublished or data["published"])
        and (not opendata or data["is_open_data"])
        and (not withvisuals or data["has_visuals"])
        and (not data_type or data_type == [None] or data["data_type"] in data_type)
        and (not source_ids or source_ids.intersection(set(data["source_tag_ids"])))
        and (not topic_ids or topic_ids.intersection(set(data["topic_tag_ids"])))
        and (not user_accessible or data["has_access"])
        and (not user_inaccessible or not data["has_access"])
    )


def has_unpublished_dataset_access(user):
    access = user.is_superuser
    for dataset_type in DataSetType:
        access = access or user.has_perm(
            dataset_type_to_manage_unpublished_permission_codename(dataset_type.value)
        )

    return access


def _get_tags_as_dict():
    """
    Gets all tags and returns them as a dictionary keyed by the tag.id as a string
    @return:
    """
    tags = Tag.objects.all()
    tags_dict = {}

    for tag in tags:
        tags_dict[str(tag.id)] = model_to_dict(tag)

    return tags_dict


@require_GET
def find_datasets(request):
    ###############
    # Validate form

    form = DatasetSearchForm(request, request.GET)

    if not form.is_valid():
        logger.warning(form.errors)
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    data_types = form.fields[
        "data_type"
    ].choices  # Cache these now, as we annotate them with result numbers later which we don't want here.

    ###############################################
    # Find all results, and matching filter numbers

    filters = form.get_filters()

    all_visible_datasets, matched_datasets = search_for_datasets(
        request.user, filters, _matches_filters
    )

    form.annotate_and_update_filters(
        all_visible_datasets,
        matcher=_matches_filters,
    )

    ####################################
    # Select the current page of results

    paginator = Paginator(
        matched_datasets,
        settings.SEARCH_RESULTS_DATASETS_PER_PAGE,
    )

    datasets = paginator.get_page(request.GET.get("page"))

    ########################################################
    # Augment results with tags, avoiding queries-per-result

    tags_dict = _get_tags_as_dict()
    for dataset in datasets:
        dataset["sources"] = [
            tags_dict.get(str(source_id)) for source_id in dataset["source_tag_ids"]
        ]
        dataset["topics"] = [tags_dict.get(str(topic_id)) for topic_id in dataset["topic_tag_ids"]]

    ######################################################################
    # Augment results with last updated dates, avoiding queries-per-result

    # Data structures to quickly look up datasets as needed further down

    datasets_by_type = defaultdict(list)
    datasets_by_type_id = {}
    for dataset in datasets:
        datasets_by_type[dataset["data_type"]].append(dataset)
        datasets_by_type_id[(dataset["data_type"], dataset["id"])] = dataset

    # Reference datasets

    reference_datasets = ReferenceDataset.objects.filter(
        uuid__in=tuple(dataset["id"] for dataset in datasets_by_type[DataSetType.REFERENCE.value])
    )
    for reference_dataset in reference_datasets:
        dataset = datasets_by_type_id[(DataSetType.REFERENCE.value, reference_dataset.uuid)]
        try:
            # If the reference dataset csv table doesn't exist we
            # get an unhandled relation does not exist error
            # this is currently only a problem with integration tests
            dataset["last_updated"] = reference_dataset.data_last_updated
        except ProgrammingError as e:
            logger.error(e)
            dataset["last_updated"] = None

    # Master datasets and datacuts together to minimise metadata table queries

    master_datasets = MasterDataset.objects.filter(
        id__in=tuple(dataset["id"] for dataset in datasets_by_type[DataSetType.MASTER.value])
    ).prefetch_related("sourcetable_set")
    datacut_datasets = DataCutDataset.objects.filter(
        id__in=tuple(dataset["id"] for dataset in datasets_by_type[DataSetType.DATACUT.value])
    ).prefetch_related(
        Prefetch(
            "customdatasetquery_set",
            queryset=CustomDatasetQuery.objects.prefetch_related("tables"),
        )
    )
    databases = {database.id: database for database in Database.objects.all()}

    tables_and_last_updated_dates = datasets_db.get_all_tables_last_updated_date(
        [
            (databases[table.database_id].memorable_name, table.schema, table.table)
            for master_dataset in master_datasets
            for table in master_dataset.sourcetable_set.all()
        ]
        + [
            (databases[query.database_id].memorable_name, table.schema, table.table)
            for datacut_dataset in datacut_datasets
            for query in datacut_dataset.customdatasetquery_set.all()
            for table in query.tables.all()
        ]
    )

    if form.cleaned_data["q"]:
        log_event(
            request.user,
            EventLog.TYPE_DATASET_FIND_FORM_QUERY,
            extra={
                "query": form.cleaned_data["q"],
                "number_of_results": len(matched_datasets),
            },
        )

    def _without_none(it):
        return (val for val in it if val is not None)

    for master_dataset in master_datasets:
        dataset = datasets_by_type_id[(DataSetType.MASTER.value, master_dataset.id)]
        dataset["last_updated"] = max(
            _without_none(
                (
                    tables_and_last_updated_dates[databases[table.database_id].memorable_name].get(
                        (table.schema, table.table)
                    )
                    for table in master_dataset.sourcetable_set.all()
                )
            ),
            default=None,
        )

    for datacut_dataset in datacut_datasets:
        dataset = datasets_by_type_id[(DataSetType.DATACUT.value, datacut_dataset.id)]
        last_updated_dates_for_queries = (
            (
                tables_and_last_updated_dates[databases[query.database_id].memorable_name].get(
                    (table.schema, table.table)
                )
                for table in query.tables.all()
            )
            for query in datacut_dataset.customdatasetquery_set.all()
        )
        dataset["last_updated"] = max(
            _without_none(
                (
                    min(_without_none(last_updated_dates_for_query), default=None)
                    for last_updated_dates_for_query in last_updated_dates_for_queries
                )
            ),
            default=None,
        )

    # Visualisations

    visualisation_datasets = VisualisationCatalogueItem.objects.filter(
        id__in=tuple(
            dataset["id"] for dataset in datasets_by_type[DataSetType.VISUALISATION.value]
        )
    ).prefetch_related("visualisationlink_set")
    for visualisation_dataset in visualisation_datasets:
        dataset = datasets_by_type_id[(DataSetType.VISUALISATION.value, visualisation_dataset.id)]
        dataset["last_updated"] = max(
            _without_none(
                (
                    link.data_source_last_updated
                    for link in visualisation_dataset.visualisationlink_set.all()
                )
            ),
            default=None,
        )

    return render(
        request,
        "datasets/index.html",
        {
            "form": form,
            "query": filters.query,
            "datasets": datasets,
            "data_type": dict(data_types),
            "show_admin_filters": has_unpublished_dataset_access(request.user),
            "DATASET_FINDER_FLAG": settings.DATASET_FINDER_ADMIN_ONLY_FLAG,
            "search_type": "searchBar" if filters.query else "noSearch",
            "has_filters": filters.has_filters(),
        },
    )


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def _is_visualisation(self):
        return isinstance(self.object, VisualisationCatalogueItem)

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["dataset_uuid"], self.request.user)

    @csp_update(frame_src=settings.QUICKSIGHT_DASHBOARD_HOST)
    def get(self, request, *args, **kwargs):
        log_event(
            request.user,
            EventLog.TYPE_DATASET_VIEW,
            self.get_object(),
            extra={
                "path": request.get_full_path(),
                "reference_dataset_version": self.get_object().published_at,
            },
        )
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
            "MasterDatasetInfo", ("source_table", "code_snippets", "columns", "tools_links")
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
                tools_links=get_tools_links_for_user(self.request.user, self.request.scheme),
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
            ("datacut_link", "can_show_link", "code_snippets", "columns", "tools_links"),
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
                tools_links=get_tools_links_for_user(self.request.user, self.request.scheme),
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
        ctx["DATA_UPLOADER_UI_FLAG"] = settings.DATA_UPLOADER_UI_FLAG

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
    dataset = find_dataset(dataset_uuid, request.user)

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
def toggle_bookmark(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid, request.user)
    dataset.toggle_bookmark(request.user)

    return HttpResponseRedirect(dataset.get_absolute_url())


@require_POST
def set_bookmark(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid, request.user)
    dataset.set_bookmark(request.user)
    return HttpResponse(status=200)


@require_POST
def unset_bookmark(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid, request.user)
    dataset.unset_bookmark(request.user)
    return HttpResponse(status=200)


class ReferenceDatasetDownloadView(DetailView):
    def post(self, request, *args, **kwargs):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), request.user, ReferenceDataset)
        log_event(
            request.user,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
            dataset,
            extra={
                "path": request.get_full_path(),
                "reference_dataset_version": dataset.published_version,
                "format": self.kwargs.get("format"),
            },
        )
        return HttpResponse(status=200)


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

        client = get_s3_client()
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
        dataset = find_dataset(dataset_uuid, request.user, MasterDataset)
        source_table = get_object_or_404(SourceTable, id=table_uuid, dataset=dataset)
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
        dataset = find_dataset(dataset_uuid, request.user, ReferenceDataset)
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
        dataset = find_dataset(dataset_uuid, request.user, ReferenceDataset)
        log_event(
            request.user,
            EventLog.TYPE_REFERENCE_DATASET_VIEW,
            dataset,
            extra={
                "path": request.get_full_path(),
                "reference_dataset_version": dataset.published_version,
            },
        )
        return render(
            request,
            "datasets/reference_dataset_grid.html",
            context={"model": dataset},
        )


class RelatedDataView(View):
    def get(self, request, dataset_uuid):
        dataset = find_dataset(dataset_uuid, request.user)

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
        dataset = find_dataset(dataset_uuid, request.user)
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
        dataset = find_dataset(dataset_uuid, request.user, kwargs["model_class"])

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

    def dispatch(self, request, *args, **kwargs):
        source = self.get_object()
        if not source.data_grid_enabled:
            raise DatasetPreviewDisabledError(source.dataset)

        if not source.dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(source.dataset)

        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs["dataset_uuid"], self.request.user)
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["object_id"],
        )


class DataGridDataView(DetailView):
    def _user_can_access(self):
        source = self.get_object()
        return source.dataset.user_has_access(self.request.user) and source.data_grid_enabled

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), self.request.user)
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["object_id"],
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
            extra = {
                "correlation_id": str(uuid.uuid4()),
                **serializers.serialize("python", [source])[0],
            }

            log_event(
                request.user,
                EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
                source.dataset,
                extra=extra,
            )

            def write_metrics_to_eventlog(log_data):
                logger.debug("write_metrics_to_eventlog %s", log_data)

                log_data.update(extra)
                log_event(
                    request.user,
                    EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE,
                    source.dataset,
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
        dataset = find_dataset(dataset_uuid, request.user, model_class)

        if not dataset.user_has_access(request.user):
            return HttpResponseForbidden()

        visualisation = dataset.visualisations.get(id=object_id)
        vega_definition = self._get_vega_definition(visualisation)

        return JsonResponse(vega_definition)


class DatasetVisualisationView(View):
    def get(self, request, dataset_uuid, object_id, **kwargs):
        model_class = kwargs["model_class"]
        dataset = find_dataset(dataset_uuid, self.request.user, model_class)

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
        dataset = find_dataset(dataset_uuid, self.request.user, DataCutDataset)
        try:
            query = CustomDatasetQuery.objects.get(id=query_id, dataset__id=dataset_uuid)
        except CustomDatasetQuery.DoesNotExist:
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
        dataset = find_dataset(self.kwargs["dataset_uuid"], self.request.user)
        if self.kwargs["model_class"] == ReferenceDataset:
            return dataset
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["source_id"],
        )


class DatasetChartView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_PUBLISH_CHARTS_FLAG

    def get_object(self):
        dataset = find_dataset(
            self.kwargs["dataset_uuid"], self.request.user, self.kwargs["model_class"]
        )
        return dataset.charts.get(id=self.kwargs["object_id"])

    @csp_update(SCRIPT_SRC=["'unsafe-eval'", "blob:"], IMG_SRC=["blob:"])
    def get(self, request, **kwargs):
        chart = self.get_object()
        if not chart.dataset.user_has_access(request.user):
            return HttpResponseForbidden()
        return render(
            request,
            "datasets/charts/chart.html",
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


class EditBaseView(View):
    obj = None
    summary: str = None

    def dispatch(self, request, *args, **kwargs):
        try:
            dataset = DataSet.objects.live().get(pk=self.kwargs.get("pk"))
        except DataSet.DoesNotExist:
            dataset = None
            try:
                visualisation_catalogue_item = VisualisationCatalogueItem.objects.live().get(
                    pk=self.kwargs.get("pk")
                )
            except VisualisationCatalogueItem.DoesNotExist:
                raise Http404  # pylint: disable=W0707
        if "summary_id" in self.kwargs:
            self.summary = get_object_or_404(
                PendingAuthorizedUsers.objects.all(), pk=self.kwargs.get("summary_id")
            )
        self.obj = dataset or visualisation_catalogue_item
        if (
            request.user
            not in [
                self.obj.information_asset_owner,
                self.obj.information_asset_manager,
            ]
            and not request.user.is_superuser
        ):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class DatasetEditView(EditBaseView, UpdateView):
    model = DataSet
    form_class = DatasetEditForm
    template_name = "datasets/edit_dataset.html"

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        return {
            "enquiries_contact": self.object.enquiries_contact.email
            if self.object.enquiries_contact
            else "",
            "authorized_email_domains": ",".join(self.object.authorized_email_domains),
        }

    def form_valid(self, form):
        if "authorized_email_domains" in form.changed_data:
            log_permission_change(
                self.request.user,
                self.object,
                EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
                {"authorized_email_domains": self.object.authorized_email_domains},
                f"authorized_email_domains set to {self.object.authorized_email_domains}",
            )

            # As the dataset's access type has changed, clear cached credentials for all
            # users to ensure they either:
            #   - lose access if it went from REQUIRES_AUTHENTICATION/OPEN to REQUIRES_AUTHORIZATION
            #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION/OPEN
            invalidate_data_explorer_user_cached_credentials()
            invalidate_superset_user_cached_credentials()
        messages.success(self.request, "Dataset updated")
        return super().form_valid(form)


class VisualisationCatalogueItemEditView(EditBaseView, UpdateView):
    model = VisualisationCatalogueItem
    form_class = VisualisationCatalogueItemEditForm
    template_name = "datasets/edit_visualisation_catalogue_item.html"

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        return {
            "enquiries_contact": self.object.enquiries_contact.email
            if self.object.enquiries_contact
            else "",
            "secondary_enquiries_contact": self.object.secondary_enquiries_contact.email
            if self.object.secondary_enquiries_contact
            else "",
            "authorized_email_domains": ",".join(self.object.authorized_email_domains),
        }

    def form_valid(self, form):
        if "authorized_email_domains" in form.changed_data:
            log_permission_change(
                self.request.user,
                self.object,
                EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
                {"authorized_email_domains": self.object.authorized_email_domains},
                f"authorized_email_domains set to {self.object.authorized_email_domains}",
            )

            # As the dataset's access type has changed, clear cached credentials for all
            # users to ensure they either:
            #   - lose access if it went from REQUIRES_AUTHENTICATION/OPEN to REQUIRES_AUTHORIZATION
            #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION/OPEN
            invalidate_data_explorer_user_cached_credentials()
            invalidate_superset_user_cached_credentials()
        messages.success(self.request, "Dataset updated")
        return super().form_valid(form)


class UserSearchFormView(EditBaseView, FormView):
    form_class = UserSearchForm
    form: None

    def form_valid(self, form):
        self.form = form
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get("search_query")
        if search_query:
            email_filter = Q(email__icontains=search_query)
            name_filter = Q(first_name__icontains=search_query) | Q(
                last_name__icontains=search_query
            )
            users = get_user_model().objects.filter(Q(email_filter | name_filter))
            context["search_results"] = users
            context["search_query"] = search_query
        context["obj"] = self.obj
        context["obj_edit_url"] = (
            reverse("datasets:edit_dataset", args=[self.obj.pk])
            if isinstance(self.obj, DataSet)
            else reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.pk])
        )
        return context


class DatasetEnquiriesContactSearchView(UserSearchFormView):
    template_name = "datasets/search_enquiries_contact.html"

    def get_success_url(self):
        url = (
            reverse(
                "datasets:search_enquiries_contact",
                args=[
                    self.obj.pk,
                ],
            )
            + "?search_query="
            + self.form.cleaned_data["search"]
        )
        if self.request.GET.get("secondary_enquiries_contact"):
            url = (
                url
                + "&secondary_enquiries_contact="
                + self.request.GET.get("secondary_enquiries_contact")
            )
        return url


class DatasetSecondaryEnquiriesContactSearchView(UserSearchFormView):
    template_name = "datasets/search_secondary_enquiries_contact.html"

    def get_success_url(self):
        url = (
            reverse(
                "datasets:search_secondary_enquiries_contact",
                args=[
                    self.obj.pk,
                ],
            )
            + "?search_query="
            + self.form.cleaned_data["search"]
        )
        if self.request.GET.get("enquiries_contact"):
            url = url + "&enquiries_contact=" + self.request.GET.get("enquiries_contact")
        return url


class DatasetEditPermissionsView(EditBaseView, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        if isinstance(self.obj, DataSet):
            permissions = DataSetUserPermission.objects.filter(dataset=self.obj)
        else:
            permissions = VisualisationUserPermission.objects.filter(visualisation=self.obj)

        users = json.dumps([p.user.id for p in permissions])
        summary = PendingAuthorizedUsers.objects.create(created_by=request.user, users=users)
        return HttpResponseRedirect(
            reverse("datasets:edit_permissions_summary", args=[self.obj.id, summary.id])
        )


class DatasetEditPermissionsSummaryView(EditBaseView, TemplateView):
    template_name = "datasets/edit_permissions_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["obj"] = self.obj
        context["obj_edit_url"] = (
            reverse("datasets:edit_dataset", args=[self.obj.pk])
            if isinstance(self.obj, DataSet)
            else reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.pk])
        )

        context["summary"] = self.summary
        context["authorised_users"] = get_user_model().objects.filter(
            id__in=json.loads(self.summary.users if self.summary.users else "[]")
        )
        return context

    def post(self, request, *args, **kwargs):
        authorized_users = set(
            get_user_model().objects.filter(
                id__in=json.loads(self.summary.users if self.summary.users else "[]")
            )
        )
        if isinstance(self.obj, DataSet):
            process_dataset_authorized_users_change(
                authorized_users, request.user, self.obj, False, False, True
            )
            messages.success(request, "Dataset permissions updated")
            return HttpResponseRedirect(reverse("datasets:edit_dataset", args=[self.obj.id]))
        else:
            process_visualisation_catalogue_item_authorized_users_change(
                authorized_users, request.user, self.obj, False, False
            )
            messages.success(request, "Visualisation permissions updated")
            return HttpResponseRedirect(
                reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.id])
            )


class DatasetAuthorisedUsersSearchView(UserSearchFormView):
    template_name = "datasets/search_authorised_users.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary_id"] = self.kwargs.get("summary_id")
        return context

    def get_success_url(self):
        return (
            reverse(
                "datasets:search_authorized_users",
                args=[self.obj.pk, self.kwargs.get("summary_id")],
            )
            + "?search_query="
            + self.form.cleaned_data["search"]
        )


class DatasetAddAuthorisedUserView(EditBaseView, View):
    def get(self, request, *args, **kwargs):
        summary = PendingAuthorizedUsers.objects.get(id=self.kwargs.get("summary_id"))
        user = get_user_model().objects.get(id=self.kwargs.get("user_id"))

        users = json.loads(summary.users if summary.users else "[]")
        if user.id not in users:
            users.append(user.id)
            summary.users = json.dumps(users)
            summary.save()

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_permissions_summary",
                args=[
                    self.obj.id,
                    self.kwargs.get("summary_id"),
                ],
            )
        )


class DatasetRemoveAuthorisedUserView(EditBaseView, View):
    def get(self, request, *args, **kwargs):
        summary = PendingAuthorizedUsers.objects.get(id=self.kwargs.get("summary_id"))
        user = get_user_model().objects.get(id=self.kwargs.get("user_id"))

        users = json.loads(summary.users if summary.users else "[]")
        if user.id in users:
            summary.users = json.dumps([user_id for user_id in users if user_id != user.id])
            summary.save()

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_permissions_summary",
                args=[
                    self.obj.id,
                    self.kwargs.get("summary_id"),
                ],
            )
        )


class SelectChartSourceView(WaffleFlagMixin, FormView):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG
    form_class = ChartSourceSelectForm
    template_name = "datasets/charts/select_chart_source.html"

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs["pk"], self.request.user, DataSet)
        if not dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(dataset)
        return dataset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["dataset"] = self.get_object()
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["dataset"] = self.get_object()
        return kwargs

    def form_valid(self, form):
        dataset = self.get_object()
        source_id = form.cleaned_data["source"]
        source = dataset.get_related_source(source_id)
        if source is None:
            raise Http404
        chart = ChartBuilderChart.objects.create_from_source(source, self.request.user)
        run_chart_builder_query.delay(chart.id)
        if source.data_grid_enabled:
            return HttpResponseRedirect(
                reverse("datasets:filter_chart_data", args=(dataset.id, source.id))
            )
        return HttpResponseRedirect(f"{chart.get_edit_url()}?prev={self.request.path}")


class FilterChartDataView(WaffleFlagMixin, DetailView):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG
    form_class = ChartSourceSelectForm
    template_name = "datasets/charts/filter_chart_data.html"
    context_object_name = "source"

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs["pk"], self.request.user, DataSet)
        if not dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(dataset)
        source = dataset.get_related_source(self.kwargs["source_id"])
        if source is None:
            raise Http404
        return source


class AggregateChartDataViewView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG

    def post(self, request, dataset_uuid, source_id, *args, **kwargs):
        dataset = find_dataset(dataset_uuid, self.request.user)
        source = dataset.get_related_source(source_id)
        if source is None:
            raise Http404

        filters = {}
        for filter_data in [json.loads(x) for x in request.POST.getlist("filters")]:
            filters.update(filter_data)

        columns = [
            x
            for x in source.get_column_config()
            if x["field"] in request.POST.getlist("columns", [])
        ]

        return render(
            request,
            "datasets/charts/aggregate.html",
            context={
                "dataset": dataset,
                "source": source,
                "form": ChartAggregateForm(
                    columns=columns,
                    initial={
                        "columns": columns,
                        "filters": filters,
                        "sort_direction": request.POST.get("sortDir", "ASC"),
                        "sort_field": request.POST.get("sortField", "1"),
                    },
                ),
            },
        )


class CreateGridChartView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG

    def post(self, request, dataset_uuid, source_id, *args, **kwargs):
        dataset = find_dataset(dataset_uuid, self.request.user)
        source = dataset.get_related_source(source_id)
        if source is None:
            raise Http404

        columns = json.loads(request.POST.get("columns"))
        form = ChartAggregateForm(
            request.POST,
            columns=columns,
            initial={
                "columns": columns,
            },
        )

        if not form.is_valid():
            # Ideally we would redirect here but we need to keep the json
            # post data from the grid and so we just re-display the form
            # to let the user correct errors
            return render(
                request,
                "datasets/charts/aggregate.html",
                context={
                    "dataset": dataset,
                    "source": source,
                    "form": form,
                },
            )

        chart_data = form.cleaned_data

        original_query = source.get_data_grid_query()
        query, params = build_filtered_dataset_query(
            original_query,
            json.loads(request.POST.get("columns", "[]")),
            {
                "filters": chart_data["filters"],
                "sortDir": chart_data["sort_direction"],
                "sortField": chart_data["sort_field"],
            },
        )

        if chart_data["aggregate"] != AggregationType.NONE.value:
            query = (
                sql.SQL("SELECT {}, {}({}) FROM (").format(
                    sql.Identifier(chart_data["group_by"]),
                    sql.Identifier(chart_data["aggregate"]),
                    sql.Literal("*")
                    if chart_data["aggregate"] == "count"
                    else sql.Identifier(chart_data["aggregate_field"]),
                )
                + query
                + sql.SQL(") a ")
                + sql.SQL("GROUP by 1;")
            )

        db_name = list(settings.DATABASES_DATA.items())[0][0]
        with connections[db_name].cursor() as cursor:
            full_query = cursor.mogrify(query, params).decode()

        chart = ChartBuilderChart.objects.create_from_sql(str(full_query), request.user, db_name)
        chart.chart_config.update(
            {
                "xaxis": {"type": "category", "autorange": True},
                "yaxis": {"type": "linear", "autorange": True},
                "traces": [
                    {
                        "meta": {
                            "columnNames": {
                                "x": chart_data["group_by"],
                                "y": chart_data["aggregate"],
                            }
                        },
                        "mode": "markers",
                        "name": "Plot 0",
                        "type": "bar",
                        "xsrc": chart_data["group_by"],
                        "ysrc": chart_data["aggregate"],
                        "labelsrc": chart_data["group_by"],
                        "valuesrc": chart_data["aggregate"],
                    }
                ],
            }
        )
        chart.save()
        run_chart_builder_query.delay(chart.id)
        return HttpResponseRedirect(
            f"{chart.get_edit_url()}?prev="
            + reverse("datasets:filter_chart_data", args=(dataset.id, source.id))
        )


class DatasetChartsView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_PUBLISH_CHARTS_FLAG

    @csp_update(SCRIPT_SRC=["'unsafe-eval'", "blob:"])
    def get(self, request, **kwargs):
        dataset = find_dataset(self.kwargs["dataset_uuid"], self.request.user, DataSet)
        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        return render(
            self.request,
            "datasets/charts/charts.html",
            context={"charts": dataset.related_charts(), "dataset": dataset},
        )
