from abc import ABCMeta, abstractmethod
from collections import namedtuple
from contextlib import closing
import csv
import io
from itertools import chain
import json
from typing import Set

import boto3
import waffle
from botocore.exceptions import ClientError
from csp.decorators import csp_update
from psycopg2 import sql
from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.aggregates.general import ArrayAgg, BoolOr
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import (
    F,
    IntegerField,
    Q,
    Value,
    Case,
    When,
    BooleanField,
    QuerySet,
)
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import DetailView

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.constants import DataSetType, DataLinkType
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    streaming_query_response,
    table_data,
    view_exists,
    get_random_data_sample,
)
from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.forms import (
    DatasetSearchForm,
    EligibilityCriteriaForm,
    RequestAccessForm,
)
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataSet,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    SourceView,
    VisualisationCatalogueItem,
    SourceTable,
)
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
    find_dataset,
    find_visualisation,
    find_dataset_or_visualisation,
    get_code_snippets,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.notify import generate_token, send_email
from dataworkspace.zendesk import (
    create_zendesk_ticket,
    create_support_request,
    get_people_url,
)


def get_datasets_data_for_user_matching_query(
    datasets: QuerySet, query, use=None, user=None, id_field='id'
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
            reference_type = DataSetType.REFERENCE.value
            reference_perm = dataset_type_to_manage_unpublished_permission_codename(
                reference_type
            )

            if user.has_perm(reference_perm):
                visibility_filter |= Q(published=False)

        if datasets.model is DataSet:
            master_type, datacut_type = (
                DataSetType.MASTER.value,
                DataSetType.DATACUT.value,
            )
            master_perm = dataset_type_to_manage_unpublished_permission_codename(
                master_type
            )
            datacut_perm = dataset_type_to_manage_unpublished_permission_codename(
                datacut_type
            )

            if user.has_perm(master_perm):
                visibility_filter |= Q(published=False, type=master_type)

            if user.has_perm(datacut_perm):
                visibility_filter |= Q(published=False, type=datacut_type)

    datasets = datasets.filter(visibility_filter)

    # Filter out datasets that don't match the search terms
    search = (
        SearchVector('name', weight='A', config='english')
        + SearchVector('short_description', weight='B', config='english')
        + SearchVector(
            StringAgg('tags__name', delimiter='\n'), weight='B', config='english'
        )
    )
    search_query = SearchQuery(query, config='english')

    datasets = datasets.annotate(
        search=search, search_rank=SearchRank(search, search_query)
    )

    if query:
        datasets = datasets.filter(search=search_query)

    # Mark up whether the user can access the data in the dataset.
    access_filter = Q()

    if user and datasets.model is not ReferenceDataset:
        access_filter &= (
            Q(user_access_type='REQUIRES_AUTHENTICATION')
            & (
                Q(datasetuserpermission__user=user)
                | Q(datasetuserpermission__isnull=True)
            )
        ) | Q(
            user_access_type='REQUIRES_AUTHORIZATION', datasetuserpermission__user=user
        )

    datasets = datasets.annotate(
        _has_access=Case(
            When(access_filter, then=True), default=False, output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    # Pull in the source tag IDs for the dataset
    datasets = datasets.annotate(
        source_tag_ids=ArrayAgg(
            'tags', filter=Q(tags__type=TagType.SOURCE.value), distinct=True
        )
    )
    datasets = datasets.annotate(
        source_tag_names=ArrayAgg(
            'tags__name', filter=Q(tags__type=TagType.SOURCE.value), distinct=True
        )
    )

    # Pull in the topic tag IDs for the dataset
    datasets = datasets.annotate(
        topic_tag_ids=ArrayAgg(
            'tags', filter=Q(tags__type=TagType.TOPIC.value), distinct=True
        )
    )
    datasets = datasets.annotate(
        topic_tag_names=ArrayAgg(
            'tags__name', filter=Q(tags__type=TagType.TOPIC.value), distinct=True
        )
    )

    # Define a `purpose` column denoting the dataset type.
    if is_reference_query:
        datasets = datasets.annotate(
            purpose=Value(DataSetType.REFERENCE.value, IntegerField())
        )
    else:
        datasets = datasets.annotate(purpose=F('type'))

    # We are joining on the user permissions table to determine `_has_access`` to the dataset, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    datasets = datasets.values(
        id_field,
        'name',
        'slug',
        'short_description',
        'search_rank',
        'source_tag_names',
        'source_tag_ids',
        'topic_tag_names',
        'topic_tag_ids',
        'purpose',
        'published',
        'published_at',
    ).annotate(has_access=BoolOr('_has_access'))

    return datasets.values(
        id_field,
        'name',
        'slug',
        'short_description',
        'search_rank',
        'source_tag_names',
        'source_tag_ids',
        'topic_tag_names',
        'topic_tag_ids',
        'purpose',
        'published',
        'published_at',
        'has_access',
    )


def get_visualisations_data_for_user_matching_query(
    visualisations: QuerySet, query, user=None
):
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
            dataset_type_to_manage_unpublished_permission_codename(
                DataSetType.VISUALISATION.value
            )
        )
    ):
        visualisations = visualisations.filter(published=True)

    # Filter out visualisations that don't match the search terms
    search = SearchVector('name', weight='A', config='english') + SearchVector(
        'short_description', weight='B', config='english'
    )
    search_query = SearchQuery(query, config='english')

    visualisations = visualisations.annotate(
        search=search, search_rank=SearchRank(search, search_query)
    )

    if query:
        visualisations = visualisations.filter(search=search_query)

    # Mark up whether the user can access the visualisation.
    if user:
        access_filter = (
            Q(user_access_type='REQUIRES_AUTHENTICATION')
            & (
                Q(visualisationuserpermission__user=user)
                | Q(visualisationuserpermission__isnull=True)
            )
        ) | Q(
            user_access_type='REQUIRES_AUTHORIZATION',
            visualisationuserpermission__user=user,
        )
    else:
        access_filter = Q()

    visualisations = visualisations.annotate(
        _has_access=Case(
            When(access_filter, then=True), default=False, output_field=BooleanField(),
        )
        if access_filter
        else Value(True, BooleanField()),
    )

    # Pull in the source tag IDs for the dataset
    visualisations = visualisations.annotate(
        source_tag_ids=ArrayAgg(
            'tags', filter=Q(tags__type=TagType.SOURCE.value), distinct=True
        )
    )

    visualisations = visualisations.annotate(
        source_tag_names=ArrayAgg(
            'tags__name', filter=Q(tags__type=TagType.SOURCE.value), distinct=True
        )
    )

    # Pull in the topic tag IDs for the dataset
    visualisations = visualisations.annotate(
        topic_tag_ids=ArrayAgg(
            'tags', filter=Q(tags__type=TagType.TOPIC.value), distinct=True
        )
    )

    visualisations = visualisations.annotate(
        topic_tag_names=ArrayAgg(
            'tags__name', filter=Q(tags__type=TagType.TOPIC.value), distinct=True
        )
    )

    # Define a `purpose` column denoting the dataset type
    visualisations = visualisations.annotate(
        purpose=Value(DataSetType.VISUALISATION.value, IntegerField())
    )

    # We are joining on the user permissions table to determine `_has_access`` to the visualisation, so we need to
    # group them and remove duplicates. We aggregate all the `_has_access` fields together and return true if any
    # of the records say that access is available.
    visualisations = visualisations.values(
        'id',
        'name',
        'slug',
        'short_description',
        'search_rank',
        'source_tag_names',
        'source_tag_ids',
        'topic_tag_names',
        'topic_tag_ids',
        'purpose',
        'published',
        'published_at',
    ).annotate(has_access=BoolOr('_has_access'))

    return visualisations.values(
        'id',
        'name',
        'slug',
        'short_description',
        'search_rank',
        'source_tag_names',
        'source_tag_ids',
        'topic_tag_names',
        'topic_tag_ids',
        'purpose',
        'published',
        'published_at',
        'has_access',
    )


def _matches_filters(
    data,
    access: bool,
    unpublished: bool,
    use: Set,
    source_ids: Set,
    topic_ids: Set,
    topic_flag_active,
):
    return (
        (not access or data['has_access'])
        and (unpublished or data['published'])
        and (not use or use == [None] or data['purpose'] in use)
        and (not source_ids or source_ids.intersection(set(data['source_tag_ids'])))
        and (
            not topic_flag_active
            or (not topic_ids or topic_ids.intersection(set(data['topic_tag_ids'])))
        )
    )


def sorted_datasets_and_visualisations_matching_query_for_user(
    query, use, user, sort_by
):
    """
    Retrieves all master datasets, datacuts, reference datasets and visualisations (i.e. searchable items)
    and returns them, sorted by incoming sort field, default is desc(search_rank).
    """
    master_and_datacut_datasets = get_datasets_data_for_user_matching_query(
        DataSet.objects.live(), query, use, user=user, id_field='id'
    )

    reference_datasets = get_datasets_data_for_user_matching_query(
        ReferenceDataset.objects.live(), query, user=user, id_field='uuid'
    )

    visualisations = get_visualisations_data_for_user_matching_query(
        VisualisationCatalogueItem.objects, query, user=user
    )

    # Combine all datasets and visualisations and order them.

    sort_fields = sort_by.split(',')

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
    purposes = form.fields[
        'use'
    ].choices  # Cache these now, as we annotate them with result numbers later which we don't want here.

    if form.is_valid():
        query = form.cleaned_data.get("q")
        access = form.cleaned_data.get("access")
        unpublished = form.cleaned_data.get("unpublished")
        use = set(form.cleaned_data.get("use"))
        sort = form.cleaned_data.get("sort")
        source_ids = set(source.id for source in form.cleaned_data.get("source"))
        topic_ids = set(topic.id for topic in form.cleaned_data.get("topic"))
    else:
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    all_datasets_visible_to_user_matching_query = sorted_datasets_and_visualisations_matching_query_for_user(
        query=query, use=use, user=request.user, sort_by=sort,
    )

    # Filter out any records that don't match the selected filters. We do this in Python, not the DB, because we need
    # to run varied aggregations on the datasets in order to count how many records will be available if users apply
    # additional filters and this was difficult to do in the DB. This process will slowly degrade over time but should
    # be sufficient while the number of datasets is relatively low (hundreds/thousands).
    datasets_matching_query_and_filters = list(
        filter(
            lambda d: _matches_filters(
                d,
                bool(access),
                bool(unpublished),
                use,
                source_ids,
                topic_ids,
                waffle.flag_is_active(request, settings.FILTER_BY_TOPIC_FLAG),
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
        topic_flag_active=waffle.flag_is_active(request, settings.FILTER_BY_TOPIC_FLAG),
    )

    paginator = Paginator(
        datasets_matching_query_and_filters, settings.SEARCH_RESULTS_DATASETS_PER_PAGE,
    )

    return render(
        request,
        'datasets/index.html',
        {
            "form": form,
            "query": query,
            "datasets": paginator.get_page(request.GET.get("page")),
            "purpose": dict(purposes),
            "show_unpublished": has_unpublished_dataset_access(request.user),
        },
    )


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def _is_visualisation(self):
        return isinstance(self.object, VisualisationCatalogueItem)

    def get_object(self, queryset=None):
        dataset_uuid = self.kwargs['dataset_uuid']
        dataset = None
        try:
            dataset = ReferenceDataset.objects.live().get(uuid=dataset_uuid)
        except ReferenceDataset.DoesNotExist:
            try:
                dataset = DataSet.objects.live().get(id=dataset_uuid)
            except DataSet.DoesNotExist:
                try:
                    dataset = VisualisationCatalogueItem.objects.live().get(
                        id=dataset_uuid
                    )
                except VisualisationCatalogueItem.DoesNotExist:
                    pass

        if dataset:
            perm_codename = dataset_type_to_manage_unpublished_permission_codename(
                dataset.type
            )

            if not dataset.published and not self.request.user.has_perm(perm_codename):
                dataset = None

        if not dataset:
            raise Http404('No dataset matches the given query.')

        return dataset

    @csp_update(frame_src=settings.QUICKSIGHT_DASHBOARD_HOST)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def _get_context_data_for_master_dataset(self, ctx, **kwargs):
        source_tables = sorted(self.object.sourcetable_set.all(), key=lambda x: x.name)

        MasterDatasetInfo = namedtuple(
            'MasterDatasetInfo', ('dataset', 'code_snippets')
        )
        master_datasets_info = [
            MasterDatasetInfo(
                dataset=dataset, code_snippets=get_code_snippets(dataset),
            )
            for dataset in sorted(source_tables, key=lambda x: x.name)
        ]

        ctx.update(
            {
                'has_access': self.object.user_has_access(self.request.user),
                'master_datasets_info': master_datasets_info,
                'source_table_type': DataLinkType.SOURCE_TABLE.value,
            }
        )
        return ctx

    def _get_context_data_for_datacut_dataset(self, ctx, **kwargs):
        source_views = self.object.sourceview_set.all()
        custom_queries = self.object.customdatasetquery_set.all().prefetch_related(
            'tables'
        )
        if source_views:
            columns = datasets_db.get_columns(
                source_views[0].database.memorable_name,
                schema=source_views[0].schema,
                table=source_views[0].view,
            )
        elif custom_queries:
            columns = datasets_db.get_columns(
                custom_queries[0].database.memorable_name, query=custom_queries[0].query
            )
        else:
            columns = None

        datacuts = sorted(
            chain(self.object.sourcelink_set.all(), source_views, custom_queries),
            key=lambda x: x.name,
        )

        DatacutLinkInfo = namedtuple('DatacutLinkInfo', ('datacut', 'can_show_link'))
        datacut_links_info = [
            DatacutLinkInfo(
                datacut=datacut,
                can_show_link=datacut.can_show_link_for_user(self.request.user),
            )
            for datacut in datacuts
        ]

        query_tables = []
        for query in custom_queries:
            query_tables.extend([qt.table for qt in query.tables.all()])

        ds_tables = SourceTable.objects.filter(
            dataset__published=True, table__in=query_tables,
        ).prefetch_related('dataset')
        related_masters = [ds_table.dataset for ds_table in ds_tables]

        ctx.update(
            {
                'has_access': self.object.user_has_access(self.request.user),
                'datacut_links_info': datacut_links_info,
                'fields': columns,
                'data_hosted_externally': any(
                    not source_link.url.startswith('s3://')
                    for source_link in self.object.sourcelink_set.all()
                ),
                'custom_dataset_query_type': DataLinkType.CUSTOM_QUERY.value,
                'related_masters': set(related_masters),
            }
        )
        return ctx

    def _get_context_data_for_reference_dataset(self, ctx, **kwargs):
        records = self.object.get_records()
        total_record_count = records.count()
        preview_limit = self.get_preview_limit(total_record_count)
        records = records[:preview_limit]

        ctx.update(
            {
                'preview_limit': preview_limit,
                'record_count': total_record_count,
                'records': records,
            }
        )
        return ctx

    def _get_context_data_for_visualisation(self, ctx, **kwargs):
        ctx.update(
            {
                'has_access': self.object.user_has_access(self.request.user),
                "visualisation_links": self.object.get_visualisation_links(
                    self.request
                ),
            }
        )
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['model'] = self.object

        if self._is_reference_dataset():
            return self._get_context_data_for_reference_dataset(ctx, **kwargs)

        elif self._is_visualisation():
            return self._get_context_data_for_visualisation(ctx, **kwargs)

        elif self.object.type == DataSetType.MASTER.value:
            return self._get_context_data_for_master_dataset(ctx, **kwargs)

        elif self.object.type == DataSetType.DATACUT.value:
            return self._get_context_data_for_datacut_dataset(ctx, **kwargs)

        breakpoint()

        raise ValueError(
            f"Unknown dataset/type for {self.__class__.__name__}: {self.object}"
        )

    def get_template_names(self):
        if self._is_reference_dataset():
            return ['datasets/referencedataset_detail.html']
        elif self.object.type == DataSet.TYPE_MASTER_DATASET:
            return ['datasets/master_dataset.html']
        elif self.object.type == DataSet.TYPE_DATA_CUT:
            return ['datasets/data_cut_dataset.html']
        elif self._is_visualisation():
            return ['datasets/visualisation_catalogue_item.html']

        raise RuntimeError(f"Unknown template for {self}")

    def get_preview_limit(self, record_count):
        return min([record_count, settings.REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS])


@require_http_methods(['GET', 'POST'])
def eligibility_criteria_view(request, dataset_uuid):
    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    if request.method == 'POST':
        form = EligibilityCriteriaForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['meet_criteria']:
                return HttpResponseRedirect(
                    reverse('datasets:request_access', args=[dataset_uuid])
                )
            else:
                return HttpResponseRedirect(
                    reverse(
                        'datasets:eligibility_criteria_not_met', args=[dataset_uuid]
                    )
                )

    return render(request, 'eligibility_criteria.html', {'dataset': dataset})


@require_GET
def eligibility_criteria_not_met_view(request, dataset_uuid):
    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    return render(
        request,
        'eligibility_criteria_not_met.html',
        {
            'dataset': dataset,
            'is_visualisation': isinstance(dataset, VisualisationCatalogueItem),
        },
    )


@require_http_methods(['GET', 'POST'])
def request_access_view(request, dataset_uuid):
    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    if request.method == 'POST':
        form = RequestAccessForm(request.POST)
        if form.is_valid():
            goal = form.cleaned_data['goal']
            contact_email = form.cleaned_data['email']

            user_edit_relative = reverse(
                'admin:auth_user_change', args=[request.user.id]
            )
            user_url = request.build_absolute_uri(user_edit_relative)

            dataset_url = request.build_absolute_uri(dataset.get_absolute_url())

            if (
                isinstance(dataset, VisualisationCatalogueItem)
                and dataset.visualisation_template
            ):
                ticket_reference = _notify_visualisation_access_request(
                    request, dataset, dataset_url, contact_email, goal
                )
            else:
                ticket_reference = create_zendesk_ticket(
                    contact_email,
                    request.user,
                    goal,
                    user_url,
                    dataset.name,
                    dataset_url,
                    dataset.information_asset_owner,
                    dataset.information_asset_manager,
                )

            log_event(
                request.user,
                EventLog.TYPE_DATASET_ACCESS_REQUEST,
                dataset,
                extra={
                    'contact_email': contact_email,
                    'goal': goal,
                    'ticket_reference': ticket_reference,
                },
            )

            url = reverse('datasets:request_access_success', args=[dataset_uuid])
            return HttpResponseRedirect(f'{url}?ticket={ticket_reference}')

    return render(
        request,
        'request_access.html',
        {
            'dataset': dataset,
            'authenticated_user': request.user,
            'is_visualisation': isinstance(dataset, VisualisationCatalogueItem),
        },
    )


@require_GET
def request_access_success_view(request, dataset_uuid):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']

    dataset = find_dataset_or_visualisation(dataset_uuid, request.user)

    return render(
        request, 'request_access_success.html', {'ticket': ticket, 'dataset': dataset}
    )


def _notify_visualisation_access_request(
    request, dataset, dataset_url, contact_email, goal
):

    message = f"""
An access request has been sent to the data visualisation owner and secondary contact to process.

There is no need to action this ticket until a further notification is received.

Data visualisation: {dataset.name} ({dataset_url})

Requestor {request.user.email}
People finder link: {get_people_url(request.user.get_full_name())}

Requestor’s response to why access is needed:
{goal}

Data visualisation owner: {dataset.enquiries_contact.email}

Secondary contact: {dataset.secondary_enquiries_contact.email}

If access has not been granted to the requestor within 5 working days, this will trigger an update to this Zendesk ticket to resolve the request.
    """

    ticket_reference = create_support_request(
        request.user,
        request.user.email,
        message,
        subject=f"Data visualisation access request received - {dataset.name}",
        tag='visualisation-access-request',
    )

    give_access_url = request.build_absolute_uri(
        reverse(
            "visualisations:users-give-access",
            args=[dataset.visualisation_template.gitlab_project_id],
        )
    )
    give_access_token = generate_token(
        {'email': request.user.email, 'ticket': ticket_reference}
    ).decode('utf-8')

    for contact in set(
        [dataset.enquiries_contact.email, dataset.secondary_enquiries_contact.email]
    ):
        send_email(
            settings.NOTIFY_VISUALISATION_ACCESS_REQUEST_TEMPLATE_ID,
            contact,
            personalisation={
                "visualisation_name": dataset.name,
                "visualisation_url": dataset_url,
                "user_email": contact_email,
                "goal": goal,
                "people_url": get_people_url(request.user.get_full_name()),
                "give_access_url": f"{give_access_url}?token={give_access_token}",
            },
        )

    return ticket_reference


@require_GET
def request_visualisation_access_success_view(request, dataset_uuid):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']

    dataset = find_visualisation(dataset_uuid, request.user)

    return render(
        request, 'request_access_success.html', {'ticket': ticket, 'dataset': dataset}
    )


class ReferenceDatasetDownloadView(DetailView):
    model = ReferenceDataset

    def get_object(self, queryset=None):
        return get_object_or_404(
            ReferenceDataset.objects.live(),
            uuid=self.kwargs.get('dataset_uuid'),
            **{'published': True} if not self.request.user.is_superuser else {},
        )

    def get(self, request, *args, **kwargs):
        dl_format = self.kwargs.get('format')
        if dl_format not in ['json', 'csv']:
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
        response['Content-Disposition'] = 'attachment; filename={}-{}.{}'.format(
            ref_dataset.slug, ref_dataset.published_version, dl_format
        )

        log_event(
            request.user,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
            ref_dataset,
            extra={
                'path': request.get_full_path(),
                'reference_dataset_version': ref_dataset.published_version,
                'download_format': dl_format,
            },
        )
        ref_dataset.number_of_downloads = F('number_of_downloads') + 1
        ref_dataset.save(update_fields=['number_of_downloads'])

        if dl_format == 'json':
            response['Content-Type'] = 'application/json'
            response.write(json.dumps(list(records), cls=DjangoJSONEncoder))
        else:
            response['Content-Type'] = 'text/csv'
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
        dataset = find_dataset(self.kwargs.get('dataset_uuid'), request.user)

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        source_link = get_object_or_404(
            SourceLink, id=self.kwargs.get('source_link_id'), dataset=dataset
        )

        log_event(
            request.user,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
            source_link.dataset,
            extra={
                'path': request.get_full_path(),
                **serializers.serialize('python', [source_link])[0],
            },
        )
        dataset.number_of_downloads = F('number_of_downloads') + 1
        dataset.save(update_fields=['number_of_downloads'])

        if source_link.link_type == source_link.TYPE_EXTERNAL:
            return HttpResponseRedirect(source_link.url)

        client = boto3.client('s3')
        try:
            file_object = client.get_object(
                Bucket=settings.AWS_UPLOADS_BUCKET, Key=source_link.url
            )
        except ClientError as ex:
            try:
                return HttpResponse(
                    status=ex.response['ResponseMetadata']['HTTPStatusCode']
                )
            except KeyError:
                return HttpResponseServerError()

        response = StreamingHttpResponseWithoutDjangoDbConnection(
            file_object['Body'].iter_chunks(chunk_size=65536),
            content_type=file_object['ContentType'],
        )
        response[
            'Content-Disposition'
        ] = f'attachment; filename="{source_link.get_filename()}"'
        response['Content-Length'] = file_object['ContentLength']

        return response


class SourceDownloadMixin:
    pk_url_kwarg = 'source_id'
    event_log_type = None

    @staticmethod
    def db_object_exists(db_object):
        raise NotImplementedError()

    def get_table_data(self, db_object):
        raise NotImplementedError()

    def get(self, request, *_, **__):
        dataset = find_dataset(self.kwargs.get('dataset_uuid'), request.user)
        db_object = get_object_or_404(
            self.model, id=self.kwargs.get('source_id'), dataset=dataset
        )

        if not db_object.dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        if not self.db_object_exists(db_object):
            return HttpResponseNotFound()

        log_event(
            request.user,
            self.event_log_type,
            db_object.dataset,
            extra={
                'path': request.get_full_path(),
                **serializers.serialize('python', [db_object])[0],
            },
        )
        dataset.number_of_downloads = F('number_of_downloads') + 1
        dataset.save(update_fields=['number_of_downloads'])
        return self.get_table_data(db_object)


class SourceViewDownloadView(SourceDownloadMixin, DetailView):
    model = SourceView
    event_log_type = EventLog.TYPE_DATASET_SOURCE_VIEW_DOWNLOAD

    @staticmethod
    def db_object_exists(db_object):
        return view_exists(
            db_object.database.memorable_name, db_object.schema, db_object.view
        )

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
        dataset = find_dataset(self.kwargs.get('dataset_uuid'), request.user)

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        query = get_object_or_404(
            self.model, id=self.kwargs.get('query_id'), dataset=dataset
        )

        if not query.reviewed and not request.user.is_superuser:
            return HttpResponseForbidden()

        log_event(
            request.user,
            EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
            query.dataset,
            extra={
                'path': request.get_full_path(),
                **serializers.serialize('python', [query])[0],
            },
        )
        dataset.number_of_downloads = F('number_of_downloads') + 1
        dataset.save(update_fields=['number_of_downloads'])

        return streaming_query_response(
            request.user.email,
            query.database.memorable_name,
            sql.SQL(query.query),
            query.get_filename(),
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
        dataset = find_dataset(self.kwargs.get('dataset_uuid'), user)

        if not dataset.user_has_access(user):
            return HttpResponseForbidden()

        source_object, columns, query = self.get_preview_data(dataset)

        records = []
        sample_size = settings.DATASET_PREVIEW_NUM_OF_ROWS
        if columns:
            rows = get_random_data_sample(
                source_object.database.memorable_name, sql.SQL(query), sample_size,
            )
            for row in rows:
                record_data = {}
                for i, column in enumerate(columns):
                    record_data[column] = row[i]
                records.append(record_data)

        can_download = source_object.can_show_link_for_user(user)

        return render(
            request,
            'datasets/dataset_preview.html',
            {
                'dataset': dataset,
                'source_object': source_object,
                'fields': columns,
                'records': records,
                'preview_limit': sample_size,
                'record_count': len(records),
                'fixed_table_height_limit': 10,
                'truncate_limit': 100,
                'can_download': can_download,
                'type': source_object.type,
            },
        )


class SourceTablePreviewView(DatasetPreviewView):
    model = SourceTable

    def get_preview_data(self, dataset):
        source_table_object = get_object_or_404(
            self.model, id=self.kwargs.get('table_uuid'), dataset=dataset
        )
        database_name = source_table_object.database.memorable_name
        table_name = source_table_object.table
        schema_name = source_table_object.schema
        columns = datasets_db.get_columns(
            database_name, schema=schema_name, table=table_name
        )
        preview_query = f"""
            select * from "{schema_name}"."{table_name}"
        """
        return source_table_object, columns, preview_query


class CustomDatasetQueryPreviewView(DatasetPreviewView):
    model = CustomDatasetQuery

    def get_preview_data(self, dataset):
        query_object = get_object_or_404(
            self.model, id=self.kwargs.get('query_id'), dataset=dataset
        )

        if not query_object.reviewed and not self.request.user.is_superuser:
            raise PermissionDenied()

        database_name = query_object.database.memorable_name
        columns = datasets_db.get_columns(database_name, query=query_object.query,)
        preview_query = query_object.query

        return query_object, columns, preview_query
