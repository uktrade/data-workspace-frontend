import json
import logging
import uuid
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from itertools import chain
from typing import Set

import psycopg2
from botocore.exceptions import ClientError
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import ProgrammingError
from django.db.models import CharField, Count, F, Func, Prefetch, Q, TextField, Value
from django.db.models.functions import Cast, TruncDay
from django.forms.models import model_to_dict
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import DetailView, FormView, TemplateView, UpdateView, View
from psycopg2 import sql

from dataworkspace import datasets_db
from dataworkspace.apps.accounts.models import UserDataTableView
from dataworkspace.apps.api_v1.core.views import invalidate_superset_user_cached_credentials
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.errors import DatasetPermissionDenied, DatasetPreviewDisabledError
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    database_dsn,
    get_notification_banner,
    is_last_days_remaining_notification_banner,
    streaming_query_response,
    table_data,
    view_exists,
)
from dataworkspace.apps.datasets.constants import DataLinkType, DataSetType, TagType
from dataworkspace.apps.datasets.data_dictionary.service import DataDictionaryService
from dataworkspace.apps.datasets.forms import (
    DatasetEditForm,
    DatasetSearchForm,
    EligibilityCriteriaForm,
    RelatedDataCutsSortForm,
    RelatedMastersSortForm,
    RelatedVisualisationsSortForm,
    ReviewAccessForm,
    UserSearchForm,
    VisualisationCatalogueItemEditForm,
)
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DataSet,
    DataSetUserPermission,
    MasterDataset,
    PendingAuthorizedUsers,
    ReferenceDataset,
    SourceLink,
    SourceTable,
    SourceView,
    Tag,
    ToolQueryAuditLogTable,
    VisualisationCatalogueItem,
    VisualisationUserPermission,
)
from dataworkspace.apps.datasets.permissions.utils import (
    process_dataset_authorized_users_change,
    process_visualisation_catalogue_item_authorized_users_change,
)
from dataworkspace.apps.datasets.search import search_for_datasets
from dataworkspace.apps.datasets.utils import (
    build_filtered_dataset_query,
    clean_dataset_restrictions_on_usage,
    dataset_type_to_manage_unpublished_permission_codename,
    find_dataset,
    get_code_snippets_for_query,
    get_code_snippets_for_reference_table,
    get_code_snippets_for_table,
    get_recently_viewed_catalogue_pages,
    get_tools_links_for_user,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event, log_permission_change
from dataworkspace.apps.explorer.utils import invalidate_data_explorer_user_cached_credentials
from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.notify import send_email

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
    publisher_ids: Set,
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
    if data["is_contact"]:
        users_datasets.add("enquiries_contact")
    if data["is_editor"]:
        users_datasets.add("editor")

    return (
        (
            not selected_user_datasets
            or selected_user_datasets == [None]
            or set(selected_user_datasets).intersection(users_datasets)
        )
        and (unpublished or data["published"])
        and (not opendata or data["is_open_data"])
        and (not data_type or data_type == [None] or data["data_type"] in data_type)
        and (not source_ids or source_ids.intersection(set(data["source_tag_ids"])))
        and (not topic_ids or topic_ids.intersection(set(data["topic_tag_ids"])))
        and (not publisher_ids or publisher_ids.intersection(set(data["publisher_tag_ids"])))
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


@csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC)
def home_view(request):
    banner = get_notification_banner(request)
    return render(
        request,
        "datasets/index.html",
        {"banner": banner, "last_chance": is_last_days_remaining_notification_banner(banner)},
    )


@csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC)
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
        dataset["publishers"] = [
            tags_dict.get(str(publisher_id)) for publisher_id in dataset["publisher_tag_ids"]
        ]

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

    # Data Insights for IAMs and IAOs
    for dataset in datasets:
        get_owner_insights(dataset)

    return render(
        request,
        "datasets/data_catalogue.html",
        {
            "form": form,
            "recently_viewed_catalogue_pages": get_recently_viewed_catalogue_pages(request),
            "query": filters.query,
            "datasets": datasets,
            "data_type": dict(data_types),
            "show_admin_filters": has_unpublished_dataset_access(request.user)
            and request.user.is_superuser,
            "search_type": "searchBar" if filters.query else "noSearch",
            "has_filters": filters.has_filters(),
        },
    )


def show_pipeline_failed_message_on_dataset(source_tables):
    return not all((source_table.pipeline_last_run_success() for source_table in source_tables))


def get_owner_insights(dataset):
    if dataset["is_owner"]:
        dataset["number_of_requests"] = len(
            AccessRequest.objects.filter(
                catalogue_item_id=dataset["id"], data_access_status="waiting"
            )
        )
        dataset["count"] = EventLog.objects.filter(
            event_type=EventLog.TYPE_DATASET_VIEW,
            object_id=dataset["id"],
            timestamp__gte=datetime.now() - timedelta(days=28),
        ).count()
        source_tables = SourceTable.objects.filter(dataset_id=dataset["id"])
        dataset["source_tables_amount"] = source_tables.count()
        dataset["show_pipeline_failed_message"] = show_pipeline_failed_message_on_dataset(
            source_tables
        )
        service = DataDictionaryService()
        dataset["filled_dicts"] = 0
        for source_table in source_tables:
            items = service.get_dictionary(source_table.id).items
            matches = [column for column in items if column.definition]
            if len(matches) > 0 and len(matches) == len(items):
                dataset["filled_dicts"] += 1


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def _is_visualisation(self):
        return isinstance(self.object, VisualisationCatalogueItem)

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["dataset_uuid"], self.request.user)

    @csp_update(
        frame_src=settings.QUICKSIGHT_DASHBOARD_HOST,
        SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC,
    )
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

    def _get_publisher_text(self, model):
        publisher_text = ", ".join(
            sorted({t.name for t in self.object.tags.filter(type=TagType.PUBLISHER)})
        )
        return publisher_text

    def _get_user_tools_access(self) -> bool:
        user_has_tools_access = self.request.user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        return user_has_tools_access

    def _get_context_data_for_master_dataset(self, ctx, **kwargs):
        source_tables = sorted(
            self.object.sourcetable_set.filter(published=True).all(), key=lambda x: x.name
        )

        MasterDatasetInfo = namedtuple(
            "MasterDatasetInfo",
            (
                "source_table",
                "code_snippets",
                "columns",
                "tools_links",
                "pipeline_last_run_succeeded",
            ),
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
                pipeline_last_run_succeeded=source_table.pipeline_last_run_success(),
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
                "publisher_text": self._get_publisher_text(self.object),
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
                "show_pipeline_failed_message": not all(
                    (x.pipeline_last_run_succeeded for x in master_datasets_info)
                ),
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

        # If one or more queries to generate source columns failed raise an event
        for link_info in datacut_links_info:
            if link_info.columns is not None and len(link_info.columns) == 0:
                log_event(
                    self.request.user,
                    EventLog.TYPE_USER_DATACUT_GRID_VIEW_FAILED,
                    self.object,
                    extra={
                        "details": "Query to determine datacut columns failed to return any data"
                    },
                )
                break

        subscription = self.object.subscriptions.filter(user=self.request.user)

        datacut_tables = [
            table
            for table in datacut_links_info
            if table.datacut_link.type == DataLinkType.CUSTOM_QUERY
        ]
        datacut_links = [
            link
            for link in datacut_links_info
            if link.datacut_link.type == DataLinkType.SOURCE_LINK
        ]

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
                "publisher_text": self._get_publisher_text(self.object),
                "subscription": {
                    "current_user_is_subscribed": subscription.exists()
                    and subscription.first().is_active(),
                    "details": subscription.first(),
                },
                "has_datacut_tables": bool(datacut_tables),
                "has_datacut_links": bool(datacut_links),
            }
        )
        return ctx

    def _get_context_data_for_reference_dataset(self, ctx, **kwargs):
        records = self.object.get_records()
        total_record_count = records.count()
        preview_limit = self.get_preview_limit(total_record_count)
        records = records[:preview_limit]
        code_snippets = get_code_snippets_for_reference_table(self.object)
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
                "tools_links": get_tools_links_for_user(self.request.user, self.request.scheme),
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
                "publisher_text": self._get_publisher_text(self.object),
            }
        )
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        clean_dataset_restrictions_on_usage(self.object)

        ctx["model"] = self.object
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
            return ["datasets/details/reference_dataset.html"]
        elif self.object.type == DataSetType.MASTER:
            return ["datasets/details/sourceset_dataset.html"]
        elif self.object.type == DataSetType.DATACUT:
            return ["datasets/details/data_cut_dataset.html"]
        elif self._is_visualisation():
            return ["datasets/details/visualisation_dataset.html"]

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

    clean_dataset_restrictions_on_usage(dataset)

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


@require_POST
def log_reference_dataset_download(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid, request.user, ReferenceDataset)
    received_json_data = json.loads(request.body)
    log_event(
        request.user,
        EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
        dataset,
        extra={
            **{
                "path": request.get_full_path(),
                "reference_dataset_version": dataset.published_version,
            },
            **received_json_data,
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


class ReferenceDatasetGridView(View):
    def get(self, request, dataset_uuid):
        dataset = find_dataset(dataset_uuid, request.user, ReferenceDataset)
        code_snippets = get_code_snippets_for_reference_table(dataset)
        columns = None
        if dataset.external_database:
            columns = datasets_db.get_columns(
                dataset.external_database.memorable_name,
                schema="public",
                table=dataset.table_name,
                include_types=True,
            )
        log_event(
            self.request.user,
            EventLog.TYPE_DATA_TABLE_VIEW,
            dataset,
            extra={
                "path": self.request.get_full_path(),
                "data_table_name": dataset.name,
                "data_table_id": dataset.id,
            },
        )
        return render(
            request,
            "datasets/data-preview/reference_dataset_preview.html",
            context={
                "model": dataset,
                "code_snippets": code_snippets,
                "columns": columns,
                "tools_links": get_tools_links_for_user(self.request.user, self.request.scheme),
            },
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
                "datasets/related_content/related_data.html",
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
                "datasets/related_content/related_visualisations.html",
                context={
                    "dataset": dataset,
                    "related_visualisations": related_visualisations,
                    "form": form,
                },
            )

        return HttpResponse(status=500)


class DataCutPreviewView(DetailView):
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
        if dataset.type in [DataSetType.DATACUT, DataSetType.MASTER]:
            # collect table views from attached source tables
            if dataset.type == DataSetType.DATACUT:
                tables = dataset.customdatasetquery_set
            else:
                tables = dataset.sourcetable_set
            table_ids = tables.annotate(str_id=Cast("id", output_field=TextField())).values_list(
                "str_id", flat=True
            )
            table_view_events = EventLog.objects.filter(
                object_id__in=table_ids, event_type=EventLog.TYPE_DATA_TABLE_VIEW
            )
            table_views = (
                table_view_events.annotate(event=Value("Viewed"))
                .annotate(day=TruncDay("timestamp"))
                .annotate(email=F("user__email"))
                .annotate(
                    object=Func(
                        F("extra"),
                        Value(
                            "data_table_name"
                            if dataset.type == DataSetType.DATACUT
                            else "data_table_tablename"
                        ),
                        function="jsonb_extract_path_text",
                        output_field=CharField(),
                    ),
                )
                .values("day", "email", "object", "event")
                .annotate(count=Count("id"))
            )
        else:
            table_views = []
        if dataset.type == DataSetType.MASTER:
            # collect SQL query information from PostGres logs
            tables = list(dataset.sourcetable_set.values_list("table", flat=True))
            all_other_events = (
                ToolQueryAuditLogTable.objects.filter(table__in=tables)
                .annotate(event=Value("Queried"))
                .annotate(day=TruncDay("audit_log__timestamp"))
                .annotate(email=F("audit_log__user__email"))
                .annotate(object=F("table"))
                .values("day", "email", "object", "event")
                .annotate(count=Count("id"))
            )
        else:
            # DataCuts, Visualisation dataset events
            download_view_types = [
                EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
                EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
            ]
            all_other_events = (
                dataset.events.filter(
                    event_type__in=download_view_types
                    + [
                        EventLog.TYPE_VIEW_VISUALISATION_TEMPLATE,
                        EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
                        EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
                    ]
                )
                .annotate(
                    event=Value(
                        "Downloaded"
                        if dataset.events.filter(event_type__in=download_view_types).count() > 0
                        else "Viewed"
                    )
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
                .values("day", "email", "object", "event")
                .annotate(count=Count("id"))
            )
        # convert Django QuerySet to standard python objects to combine two different model types
        all_events = sorted(
            list(all_other_events) + list(table_views), key=lambda x: x["day"], reverse=True
        )
        return render(
            request,
            "datasets/dataset_usage_history.html",
            context={
                "dataset": dataset,
                "rows": all_events[:100],
            },
        )


class DataSourcesetDetailView(DetailView):
    template_name = "datasets/data-preview/data_sourceset_preview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        columns = datasets_db.get_columns(
            self.object.database.memorable_name,
            schema=self.object.schema,
            table=self.object.table,
            include_types=True,
        )

        ctx.update(
            {
                "has_access": self.object.dataset.user_has_access(self.request.user),
                "tools_links": get_tools_links_for_user(self.request.user, self.request.scheme),
                "code_snippets": get_code_snippets_for_table(self.object),
                "columns": columns,
            }
        )
        return ctx

    def dispatch(self, request, *args, **kwargs):
        source = self.get_object()
        if not source.data_grid_enabled:
            raise DatasetPreviewDisabledError(source.dataset)

        if not source.dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(source.dataset)

        log_event(
            self.request.user,
            EventLog.TYPE_DATA_TABLE_VIEW,
            source,
            extra={
                "path": self.request.get_full_path(),
                "data_table_name": source.name,
                "data_table_id": source.id,
                "dataset": source.dataset.name,
                **(
                    {"data_table_tablename": f"{source.schema}.{source.table}"}
                    if hasattr(source, "schema")
                    else {
                        "data_table_sourcetables": [
                            f"{s.schema}.{s.table}" for s in source.tables.all()
                        ]
                    }
                ),
            },
        )

        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs["dataset_uuid"], self.request.user)
        table_object = get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["object_id"],
        )

        return table_object


class DataCutSourceDetailView(DetailView):
    template_name = "datasets/data-preview/data_cut_preview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object

        code_snippet = get_code_snippets_for_query(self.object.query)

        columns = datasets_db.get_columns(
            database_name=self.object.database.memorable_name,
            query=self.object.query,
            include_types=True,
        )

        ctx.update(
            {
                "has_access": self.object.dataset.user_has_access(self.request.user),
                "tools_links": get_tools_links_for_user(self.request.user, self.request.scheme),
                "code_snippets": code_snippet,
                "columns": columns,
            }
        )
        return ctx

    def dispatch(self, request, *args, **kwargs):
        source = self.get_object()
        if not source.data_grid_enabled:
            raise DatasetPreviewDisabledError(source.dataset)

        if not source.dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(source.dataset)

        log_event(
            self.request.user,
            EventLog.TYPE_DATA_TABLE_VIEW,
            source,
            extra={
                "path": self.request.get_full_path(),
                "data_table_name": source.name,
                "data_table_id": source.id,
                "dataset": source.dataset.name,
                **(
                    {"data_table_tablename": f"{source.schema}.{source.table}"}
                    if hasattr(source, "schema")
                    else {
                        "data_table_sourcetables": [
                            f"{s.schema}.{s.table}" for s in source.tables.all()
                        ]
                    }
                ),
            },
        )

        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs["dataset_uuid"], self.request.user)
        table_object = get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["object_id"],
        )

        return table_object


class DataGridDataView(DetailView):
    def get_object(self, queryset=None):
        dataset = find_dataset(self.kwargs.get("dataset_uuid"), self.request.user)
        return get_object_or_404(
            self.kwargs["model_class"],
            dataset=dataset,
            pk=self.kwargs["object_id"],
        )

    def dispatch(self, request, *args, **kwargs):
        source = self.get_object()
        if not source.data_grid_enabled:
            raise DatasetPreviewDisabledError(source.dataset)

        if not source.dataset.user_has_access(self.request.user):
            raise DatasetPermissionDenied(source.dataset)

        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _get_rows(source, query, query_params):
        with psycopg2.connect(
            database_dsn(settings.DATABASES_DATA[source.database.memorable_name]),
            application_name="data-grid-data",
        ) as connection:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor,
            ) as cursor:
                # This is in the request/response cycle, so by 60 seconds of execution,
                # the user would have received a 504 anyway
                statement_timeout = 60 * 1000
                cursor.execute("SET statement_timeout = %s", (statement_timeout,))
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

        if len(column_config) == 0:
            log_event(
                request.user,
                EventLog.TYPE_USER_DATACUT_GRID_VIEW_FAILED,
                source,
                extra={"details": "Query to determine datacut columns failed to return any data"},
            )

        original_query = source.get_data_grid_query()
        download_limit = source.data_grid_download_limit
        if download_limit is None:
            download_limit = 5000
        rowcount_query, query, params = build_filtered_dataset_query(
            original_query,
            download_limit,
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
        return JsonResponse(
            {
                "rowcount": (
                    self._get_rows(source, rowcount_query, params)[0]
                    if request.GET.get("count")
                    else {"count": None}
                ),
                "download_limit": source.data_grid_download_limit,
                "records": records,
            }
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
            and request.user not in self.obj.data_catalogue_editors.all()
        ):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class DatasetEditView(EditBaseView, UpdateView):
    model = DataSet
    form_class = DatasetEditForm
    template_name = "datasets/manage_datasets/edit_dataset.html"

    @csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC, STYLE_SRC=settings.WEBPACK_SCRIPT_SRC)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        return {
            "enquiries_contact": (
                self.object.enquiries_contact.email if self.object.enquiries_contact else ""
            ),
            "authorized_email_domains": ",".join(self.object.authorized_email_domains),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unpublish_data"] = json.dumps(
            {"unpublish_url": reverse("datasets:unpublish_dataset", args=[self.obj.pk])}
        )
        return context

    def form_valid(self, form):

        if "description" in form.changed_data:

            log_permission_change(
                self.request.user,
                self.object,
                EventLog.TYPE_CHANGED_DATASET_DESCRIPTION,
                {"description": self.object.description},
                f"description set to {self.object.description}",
            )

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


class DatasetEditUnpublishView(EditBaseView, UpdateView, View):
    def post(self, request, *arg, **kwargs):
        dataset = find_dataset(kwargs["pk"], request.user)
        dataset.published = False
        dataset.save()
        # Send to zendesk to notify analyst about the page status
        return redirect('/datasets')


class VisualisationCatalogueItemEditView(EditBaseView, UpdateView):
    model = VisualisationCatalogueItem
    form_class = VisualisationCatalogueItemEditForm
    template_name = "datasets/manage_datasets/edit_visualisation_catalogue_item.html"

    @csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC, STYLE_SRC=settings.WEBPACK_SCRIPT_SRC)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        return {
            "enquiries_contact": (
                self.object.enquiries_contact.email if self.object.enquiries_contact else ""
            ),
            "secondary_enquiries_contact": (
                self.object.secondary_enquiries_contact.email
                if self.object.secondary_enquiries_contact
                else ""
            ),
            "authorized_email_domains": ",".join(self.object.authorized_email_domains),
        }

    def form_valid(self, form):

        if "description" in form.changed_data:

            log_permission_change(
                self.request.user,
                self.object,
                EventLog.TYPE_CHANGED_DATASET_DESCRIPTION,
                {"description": self.object.description},
                f"description set to {self.object.description}",
            )

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


@method_decorator(login_required, name="dispatch")
class DataCatalogueEditorsView(View):
    template_name = "datasets/manage_editors/edit_editors.html"

    def get(self, request, pk):
        dataset = find_dataset(pk, request.user)
        data_catalogue_editors = dataset.data_catalogue_editors.all()

        context = {"data_catalogue_editors": data_catalogue_editors, "obj": dataset}

        return render(request, self.template_name, context)


def remove_authorised_editor(request, pk, user_id):
    dataset = find_dataset(pk, request.user)

    user = get_user_model().objects.get(id=user_id)

    dataset.data_catalogue_editors.remove(user)
    log_event(
        request.user,
        EventLog.TYPE_DATA_CATALOGUE_EDITOR_REMOVED,
        dataset,
        extra={
            "removed_user": {
                "id": user.id,  # pylint: disable=no-member
                "email": user.email,  # pylint: disable=no-member
                "name": user.get_full_name(),  # pylint: disable=no-member
            }
        },
    )
    return HttpResponseRedirect(
        reverse(
            "datasets:edit_data_editors",
            args=[
                pk,
            ],
        )
    )


class UserSearchFormView(EditBaseView, FormView):
    form_class = UserSearchForm
    form: None

    def form_valid(self, form):
        self.form = form
        search_query = self.request.POST["search"]
        self.request.session[
            (
                f"search-query--edit-dataset-permissions--{self.obj.pk}--{self.summary.id}"
                if self.summary
                else f"search-query--edit-dataset-permissions--{self.obj.pk}"
            )
        ] = search_query

        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        try:
            initial["search"] = self.request.session[
                (
                    f"search-query--edit-dataset-permissions--{self.obj.pk}--{self.summary.id}"
                    if self.summary
                    else f"search-query--edit-dataset-permissions--{self.obj.pk}"
                )
            ]
        except KeyError:
            pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.session.get(
            f"search-query--edit-dataset-permissions--{self.obj.pk}--{self.summary.id}"
            if self.summary
            else f"search-query--edit-dataset-permissions--{self.obj.pk}"
        )
        if search_query:
            if "\n" in search_query:
                email_matches = []
                non_email_matches = []
                for query in search_query.splitlines():
                    if not query.strip():
                        continue
                    matches_for_query = get_user_model().objects.filter(
                        Q(email__iexact=query.strip())
                    )
                    for match in matches_for_query:
                        email_matches.append(match)
                    if not matches_for_query:
                        non_email_matches.append(query)
                context["search_results"] = email_matches
                context["non_matches"] = non_email_matches

            else:
                search_query = search_query.strip()
                email_filter = Q(email__icontains=search_query)
                name_filter = Q(first_name__icontains=search_query) | Q(
                    last_name__icontains=search_query
                )
                users = get_user_model().objects.filter(Q(email_filter | name_filter))
                if not users.exists() and len(search_query.split("@")) != 1:
                    users = get_user_model().objects.filter(
                        email__istartswith=search_query.split("@")[0]
                    )
                if isinstance(self.obj, DataSet):
                    permissions = DataSetUserPermission.objects.filter(dataset=self.obj)
                else:
                    permissions = VisualisationUserPermission.objects.filter(
                        visualisation=self.obj
                    )

                users_with_permission = [p.user.id for p in permissions]
                search_results = []

                for user in users:
                    search_results.append(
                        {
                            "id": user.id,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "email": user.email,
                            "has_access": user.id in users_with_permission,
                        }
                    )

                context["search_results"] = search_results
            context["search_query"] = search_query
        context["obj"] = self.obj
        context["obj_edit_url"] = (
            reverse("datasets:edit_dataset", args=[self.obj.pk])
            if isinstance(self.obj, DataSet)
            else reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.pk])
        )
        return context


class DatasetAuthorisedEditorsSearchView(UserSearchFormView):
    template_name = "datasets/search_authorised_editors.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_success_url(self):
        return reverse(
            "datasets:search_authorised_editors",
            args=[self.obj.pk],
        )


class DatasetAddAuthorisedEditorView(EditBaseView, View):
    def get(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=self.kwargs.get("user_id"))

        dataset = find_dataset(self.kwargs.get("pk"), self.request.user)

        if user not in dataset.data_catalogue_editors.all():
            dataset.data_catalogue_editors.add(user.id)

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_data_editors",
                args=[
                    dataset.id,
                ],
            )
        )


class DatasetAddAuthorisedEditorsView(EditBaseView, View):
    def post(self, request, *args, **kwargs):
        dataset = find_dataset(self.kwargs.get("pk"), self.request.user)
        selected_users = self.request.POST.getlist("selected-user")

        for selected_user in selected_users:
            user = get_object_or_404(get_user_model(), id=selected_user)
            dataset.data_catalogue_editors.add(user)
            log_event(
                request.user,
                EventLog.TYPE_DATA_CATALOGUE_EDITOR_ADDED,
                dataset,
                extra={
                    "added_user": {
                        "id": user.id,  # pylint: disable=no-member
                        "email": user.email,  # pylint: disable=no-member
                        "name": user.get_full_name(),  # pylint: disable=no-member
                    }
                },
            )

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_data_editors",
                args=[
                    dataset.id,
                ],
            )
        )


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
        iam_id = get_user_model().objects.get(id=self.obj.information_asset_manager_id).id
        iao_id = get_user_model().objects.get(id=self.obj.information_asset_owner_id).id
        user_ids = [p.user.id for p in permissions] + [iam_id, iao_id]
        users = json.dumps(user_ids)
        summary = PendingAuthorizedUsers.objects.create(created_by=request.user, users=users)
        return HttpResponseRedirect(
            reverse("datasets:edit_permissions_summary", args=[self.obj.id, summary.id])
        )


class DatasetEditPermissionsSummaryView(EditBaseView, TemplateView):
    template_name = "datasets/manage_permissions/edit_summary.html"

    @csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC, STYLE_SRC=settings.WEBPACK_SCRIPT_SRC)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        self.template_name = "datasets/manage_permissions/edit_access.html"
        context = super().get_context_data(**kwargs)
        context["user_removed"] = self.request.GET.get("user_removed", None)
        context["obj"] = self.obj
        context["obj_edit_url"] = (
            reverse("datasets:edit_dataset", args=[self.obj.pk])
            if isinstance(self.obj, DataSet)
            else reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.pk])
        )
        context["summary"] = self.summary
        # used to populate data property of ConfirmRemoveUser dialog
        data_catalogue_editors = [user.email for user in self.obj.data_catalogue_editors.all()]
        iam = get_user_model().objects.get(id=self.obj.information_asset_manager_id).email
        iao = get_user_model().objects.get(id=self.obj.information_asset_owner_id).email
        context["authorised_users"] = json.dumps(
            sorted(  # IAM or IAO should appear at top of list
                [
                    {
                        "data_catalogue_editor": u.email in data_catalogue_editors,
                        "email": u.email,
                        "first_name": u.first_name,
                        "iam": u.email == iam,
                        "iao": u.email == iao,
                        "id": u.id,
                        "last_name": u.last_name,
                        "remove_user_url": reverse(
                            "datasets:remove_authorized_user",
                            args=[self.obj.id, self.summary.id, u.id],
                        ),
                    }
                    for u in get_user_model().objects.filter(
                        id__in=json.loads(self.summary.users) if self.summary.users else []
                    )
                ],
                key=lambda x: x["first_name"],
            )
        )

        requests = AccessRequest.objects.filter(
            catalogue_item_id=self.obj.pk, data_access_status="waiting"
        )

        requested_users = []
        User = get_user_model()
        for request in requests:
            try:
                user = User.objects.get(email=request.contact_email, is_active=True)
                requested_users.append(
                    {
                        "id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "days_ago": (
                            datetime.today() - request.created_date.replace(tzinfo=None)
                        ).days
                        + 1,
                    }
                )
            except ObjectDoesNotExist:
                logger.error("User with email: %s no longer exists.", request.contact_email)
                continue
            except MultipleObjectsReturned:
                logger.error("More than one %s returned", request.contact_email)
                continue

        context["requested_users"] = requested_users
        return context

    def post(self, request, *args, **kwargs):
        authorized_users = set(
            get_user_model().objects.filter(
                id__in=json.loads(self.summary.users) if self.summary.users else []
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


class DataSetReviewAccess(EditBaseView, FormView):
    form_class = ReviewAccessForm
    template_name = "datasets/manage_permissions/review_access.html"

    def form_valid(self, form):
        [user] = get_user_model().objects.filter(id=self.kwargs["user_id"])
        summary = (
            PendingAuthorizedUsers.objects.all()
            .filter(created_by_id=self.request.user)
            .order_by("-id")
            .first()
        )
        has_granted_access = self.request.POST["action_type"] == "grant"

        if has_granted_access:
            if self.obj.type in (DataSetType.MASTER, DataSetType.DATACUT):
                permissions = DataSetUserPermission.objects.filter(dataset=self.obj)
            else:
                permissions = VisualisationUserPermission.objects.filter(visualisation=self.obj)
            users_with_permission = [p.user.id for p in permissions]
            users_with_permission.append(user.id)
            new_user_summary = PendingAuthorizedUsers.objects.create(
                created_by=self.request.user, users=json.dumps(users_with_permission)
            )
            new_user_summary.save()
            authorized_users = set(
                get_user_model().objects.filter(
                    id__in=json.loads(new_user_summary.users if new_user_summary.users else [])
                )
            )
            AccessRequest.objects.all().filter(requester_id=user.id).update(
                data_access_status="confirmed"
            )

            if self.obj.type in (DataSetType.MASTER, DataSetType.DATACUT):
                process_dataset_authorized_users_change(
                    set(authorized_users), self.request.user, self.obj, False, False, True
                )
            else:
                process_visualisation_catalogue_item_authorized_users_change(
                    set(authorized_users), self.request.user, self.obj, False, False
                )

            absolute_url = self.request.build_absolute_uri(
                reverse("datasets:dataset_detail", args=[self.obj.id])
            )
            # In Dev Ignore the API call to Zendesk and notify
            if settings.ENVIRONMENT != "Dev":
                send_email(
                    settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
                    user.email,
                    personalisation={
                        "email_address": user.email,
                        "dataset_name": self.obj.name,
                        "dataset_url": absolute_url,
                    },
                )
            messages.success(
                self.request,
                f"An email has been sent to {user.first_name} {user.last_name} to let them know they now have access.",
            )
        else:
            AccessRequest.objects.all().filter(requester_id=user.id).update(
                data_access_status="declined"
            )
            # In Dev Ignore the API call to Zendesk and notify
            if settings.ENVIRONMENT != "Dev":
                send_email(
                    settings.NOTIFY_DATASET_ACCESS_DENIED_TEMPLATE_ID,
                    user.email,
                    personalisation={
                        "email_address": user.email,
                        "dataset_name": self.obj.name,
                        "deny_reasoning": form.cleaned_data["message"],
                    },
                )
            messages.success(
                self.request,
                f"An email has been sent to {user.first_name} {user.last_name} to let them know their access request was not successful.",  # pylint: disable=line-too-long
            )
        return HttpResponseRedirect(
            reverse(
                "datasets:edit_permissions_summary",
                args=[self.obj.id, new_user_summary.id if has_granted_access else summary.id],
            )
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        args = self.kwargs
        user_id = args["user_id"]
        [user] = get_user_model().objects.filter(id=user_id)
        kwargs["requester"] = user
        return kwargs

    def get_context_data(self, **kwargs):
        args = self.kwargs
        user_id = args["user_id"]
        context = super().get_context_data(**kwargs)
        context["obj"] = self.obj
        context["eligibility_criteria"] = self.obj.eligibility_criteria
        [user] = get_user_model().objects.filter(id=user_id)
        context["full_name"] = f"{user.first_name} {user.last_name}"
        context["email"] = user.email
        access_request = AccessRequest.objects.filter(requester=user_id).latest("created_date")
        context["is_eligible"] = access_request.eligibility_criteria_met
        context["reason_for_access"] = access_request.reason_for_access
        context["obj_edit_url"] = (
            reverse("datasets:edit_dataset", args=[self.obj.pk])
            if isinstance(self.obj, DataSet)
            else reverse("datasets:edit_visualisation_catalogue_item", args=[self.obj.pk])
        )
        context["obj_manage_url"] = reverse("datasets:edit_permissions", args=[self.obj.id])
        return context


class DatasetAuthorisedUsersSearchView(UserSearchFormView):
    template_name = "datasets/search_authorised_users.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary_id"] = self.kwargs.get("summary_id")
        return context

    def get_success_url(self):
        return reverse(
            "datasets:search_authorized_users",
            args=[self.obj.pk, self.kwargs.get("summary_id")],
        )


class DatasetAddAuthorisedUserView(EditBaseView, View):

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=self.kwargs.get("user_id"))
        authorized_users = set(
            get_user_model().objects.filter(
                id__in=json.loads(self.summary.users) if self.summary.users else []
            )
        )
        authorized_users.add(user)

        if isinstance(self.obj, DataSet):
            process_dataset_authorized_users_change(
                authorized_users, request.user, self.obj, False, False, True
            )
        else:
            process_visualisation_catalogue_item_authorized_users_change(
                authorized_users, request.user, self.obj, False, False
            )

        absolute_url = self.request.build_absolute_uri(
            reverse("datasets:dataset_detail", args=[self.obj.id])
        )

        if settings.ENVIRONMENT != "Dev":
            send_email(
                settings.NOTIFY_DATASET_ACCESS_GRANTED_TEMPLATE_ID,
                user.email,
                personalisation={
                    "email_address": user.email,
                    "dataset_name": self.obj.name,
                    "dataset_url": absolute_url,
                },
            )

        messages.success(
            self.request,
            f"An email has been sent to {user.first_name} {user.last_name} to let them know they now have access.",
        )

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_permissions",
                args=[
                    self.obj.id,
                ],
            )
        )

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


class DatasetAddAuthorisedUsersView(EditBaseView, View):
    def post(self, request, *args, **kwargs):
        summary = PendingAuthorizedUsers.objects.get(id=self.kwargs.get("summary_id"))
        users = json.loads(summary.users if summary.users else "[]")
        for selected_user in self.request.POST.getlist("selected-user"):
            user = get_user_model().objects.get(id=selected_user)

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
        users = json.loads(summary.users) if summary.users else []
        if user.id in users:
            summary.users = json.dumps([user_id for user_id in users if user_id != user.id])
            summary.save()
        # get user objects from user ids as a set
        auth_users = set(get_user_model().objects.filter(id__in=json.loads(summary.users)))
        if isinstance(self.obj, DataSet):
            process_dataset_authorized_users_change(
                auth_users, request.user, self.obj, False, False, True
            )
        else:
            process_visualisation_catalogue_item_authorized_users_change(
                auth_users, request.user, self.obj, False, False
            )
        name_dataset = find_dataset(self.obj.pk, request.user).name
        url_dataset = request.build_absolute_uri(
            reverse("datasets:dataset_detail", args=[self.obj.pk])
        )
        # In Dev Ignore the API call to Zendesk and notify
        if settings.ENVIRONMENT != "Dev":
            send_email(
                settings.NOTIFY_DATASET_ACCESS_REMOVE_TEMPLATE_ID,
                user.email,
                personalisation={
                    "dataset_name": name_dataset,
                    "dataset_url": url_dataset,
                },
            )

        return HttpResponseRedirect(
            reverse(
                "datasets:edit_permissions_summary",
                args=[
                    self.obj.id,
                    self.kwargs.get("summary_id"),
                ],
            )
            + "?user_removed="
            + user.get_full_name()
        )


@require_POST
def log_data_preview_load_time(request, dataset_uuid, source_id):
    try:
        received_json_data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON data")

    dataset = find_dataset(dataset_uuid, request.user)
    source = dataset.get_related_source(source_id)
    if source is None:
        raise Http404

    extra = {
        "path": request.path,
        "data_table_name": source.name,
        "data_table_id": source.id,
        "dataset": dataset.name,
        **(
            {"data_table_tablename": f"{source.schema}.{source.table}"}
            if hasattr(source, "schema")
            else {
                "data_table_sourcetables": [f"{s.schema}.{s.table}" for s in source.tables.all()]
            }
        ),
        **received_json_data,
    }

    if received_json_data.get("status_code") == 200:
        log_event(request.user, EventLog.TYPE_DATA_PREVIEW_COMPLETE, source, extra=extra)
        return HttpResponse(status=200)
    else:
        log_event(request.user, EventLog.TYPE_DATA_PREVIEW_TIMEOUT, source, extra=extra)
        return HttpResponse(status=200)


class ReferenceDatasetGridDataView(View):
    def get(self, request, **kwargs):
        ref_dataset = get_object_or_404(
            ReferenceDataset, pk=self.kwargs["object_id"], deleted=False
        )
        return JsonResponse(
            {
                "records": ref_dataset.get_grid_data(),
            }
        )


class SaveUserDataGridView(View):
    def post(self, request, model_class, source_id):
        source = get_object_or_404(model_class, pk=source_id)
        json_data = json.loads(request.body)
        UserDataTableView.objects.update_or_create(
            user=request.user,
            source_object_id=str(source.id),
            source_content_type=ContentType.objects.get_for_model(source),
            defaults={
                "filters": json_data.get("filters"),
                "column_defs": {x["field"]: x for x in json_data.get("columnDefs", [])},
            },
        )
        return HttpResponse(status=200)

    def delete(self, request, model_class, source_id):
        source = get_object_or_404(model_class, pk=source_id)
        try:
            UserDataTableView.objects.get(
                user=request.user,
                source_object_id=str(source.id),
                source_content_type=ContentType.objects.get_for_model(source),
            ).delete()
        except UserDataTableView.DoesNotExist:
            pass
        return HttpResponse(status=200)
