from abc import ABCMeta, abstractmethod
from collections import namedtuple
from contextlib import closing
import csv
import io
from itertools import chain
import json
from typing import Union

import boto3
from botocore.exceptions import ClientError
from csp.decorators import csp_update
from psycopg2 import sql
from django.conf import settings
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import CharField, F, IntegerField, Q, Value
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
from dataworkspace.apps.applications.utils import get_quicksight_dashboard_name_url
from dataworkspace.apps.datasets.constants import DataSetType, DataLinkType
from dataworkspace.apps.core.utils import (
    StreamingHttpResponseWithoutDjangoDbConnection,
    streaming_query_response,
    table_data,
    view_exists,
    get_random_data_sample,
)
from dataworkspace.apps.datasets.forms import (
    DatasetSearchForm,
    EligibilityCriteriaForm,
    RequestAccessForm,
)
from dataworkspace.apps.datasets.model_utils import (
    get_linked_field_display_name,
    get_linked_field_identifier_name,
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
from .models import SourceTag


def filter_datasets(
    datasets: Union[ReferenceDataset, DataSet],
    query,
    access,
    source,
    use=None,
    user=None,
):
    search = (
        SearchVector('name', weight='A', config='english')
        + SearchVector('short_description', weight='B', config='english')
        + SearchVector('source_tags__name', weight='B', config='english')
    )
    search_query = SearchQuery(query, config='english')

    dataset_filter = Q(published=True)

    if user:
        if datasets.model is ReferenceDataset:
            reference_type = DataSetType.REFERENCE.value
            reference_perm = dataset_type_to_manage_unpublished_permission_codename(
                reference_type
            )

            if user.has_perm(reference_perm):
                dataset_filter |= Q(published=False)

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

            if user.has_perm(master_perm) and (not use or str(master_type) in use):
                dataset_filter |= Q(published=False, type=master_type)

            if user.has_perm(datacut_perm) and (not use or str(datacut_type) in use):
                dataset_filter |= Q(published=False, type=datacut_type)

    datasets = datasets.filter(dataset_filter).annotate(
        search=search, search_rank=SearchRank(search, search_query)
    )

    if user and access and datasets.model is not ReferenceDataset:
        access_filter = (
            Q(user_access_type='REQUIRES_AUTHENTICATION')
            & (
                Q(datasetuserpermission__user=user)
                | Q(datasetuserpermission__isnull=True)
            )
        ) | Q(
            user_access_type='REQUIRES_AUTHORIZATION', datasetuserpermission__user=user
        )
        datasets = datasets.filter(access_filter)

    if query:
        datasets = datasets.filter(search=search_query)

    if source:
        datasets = datasets.filter(source_tags__in=source)

    if use:
        datasets = datasets.filter(type__in=use)

    return datasets


def filter_visualisations(query, access, source, user=None):
    search = SearchVector('name', weight='A', config='english') + SearchVector(
        'short_description', weight='B', config='english'
    )
    search_query = SearchQuery(query, config='english')

    if user and user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(
            DataSetType.VISUALISATION.value
        )
    ):
        published_filter = Q()
    else:
        published_filter = Q(published=True)

    visualisations = VisualisationCatalogueItem.objects.filter(
        published_filter
    ).annotate(search=search, search_rank=SearchRank(search, search_query))

    if query:
        visualisations = visualisations.filter(search=search_query)

    if user and access:
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
        visualisations = visualisations.filter(access_filter)

    if source:
        visualisations = visualisations.filter(
            visualisation_template__datasetapplicationtemplatepermission__dataset__source_tags__in=source
        )

    return visualisations


@require_GET
def find_datasets(request):
    form = DatasetSearchForm(request.GET)

    if form.is_valid():
        query = form.cleaned_data.get("q")
        access = form.cleaned_data.get("access")
        use = [int(u) for u in form.cleaned_data.get("use")]
        source = form.cleaned_data.get("source")
    else:
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    # Django orders model fields before any additional fields like annotations in generated SQL statement
    # which means doing a UNION between a model field in one query and an extra field in another results
    # in different columns getting connected into a single result one (which sometimes leads to a type error
    # and sometimes succeeds with values ending up in the wrong place). To avoid this, we alias model field
    # `type` with `.annotate`, making sure it's added to the end of SELECT field list.
    datasets = (
        filter_datasets(
            DataSet.objects.live(), query, access, source, use, user=request.user
        )
        .annotate(source_tag_ids=ArrayAgg('source_tags', distinct=True))
        .annotate(purpose=F('type'))
        .values(
            'id',
            'name',
            'slug',
            'short_description',
            'search_rank',
            'source_tag_ids',
            'purpose',
        )
    )

    # Include reference datasets if required
    if not use or DataSetType.REFERENCE.value in use:
        reference_datasets = filter_datasets(
            ReferenceDataset.objects.live(), query, access, source, user=request.user
        )
        datasets = datasets.union(
            reference_datasets.annotate(source_tag_ids=ArrayAgg('source_tags'))
            .annotate(purpose=Value(DataSetType.REFERENCE.value, IntegerField()))
            .values(
                'uuid',
                'name',
                'slug',
                'short_description',
                'search_rank',
                'source_tag_ids',
                'purpose',
            )
        )

    if not use or DataSetType.VISUALISATION.value in use:
        datasets = datasets.union(
            filter_visualisations(query, access, source, user=request.user)
            .annotate(source_tag_ids=Value("{}", CharField()))
            .annotate(purpose=Value(DataSetType.VISUALISATION.value, IntegerField()))
            .values(
                'id',
                'name',
                'slug',
                'short_description',
                'search_rank',
                'source_tag_ids',
                'purpose',
            )
        )

    # Only display SourceTag filters that are associated with the dataset results
    source_tags_to_show = {
        source_tag_id
        for dataset in datasets
        for source_tag_id in dataset['source_tag_ids']
    }
    form.fields['source'].queryset = SourceTag.objects.order_by('name').filter(
        id__in=source_tags_to_show
    )

    paginator = Paginator(
        datasets.order_by('-search_rank', 'name'),
        settings.SEARCH_RESULTS_DATASETS_PER_PAGE,
    )

    return render(
        request,
        'datasets/index.html',
        {
            "form": form,
            "query": query,
            "datasets": paginator.get_page(request.GET.get("page")),
            "purpose": dict(form.fields['use'].choices),
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['model'] = self.object

        if self._is_reference_dataset():
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

        elif self._is_visualisation():
            ctx.update(
                {
                    'has_access': self.object.user_has_access(self.request.user),
                    "visualisation_links": self.object.get_visualisation_links(
                        self.request
                    ),
                }
            )
            return ctx

        source_tables = sorted(self.object.sourcetable_set.all(), key=lambda x: x.name)
        source_views = self.object.sourceview_set.all()
        custom_queries = self.object.customdatasetquery_set.all()

        if source_tables:
            columns = []
            for table in source_tables:
                columns += [
                    "{}.{}".format(table.table, column)
                    for column in datasets_db.get_columns(
                        table.database.memorable_name,
                        schema=table.schema,
                        table=table.table,
                    )
                ]
        elif source_views:
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

        data_links = sorted(
            chain(
                self.object.sourcelink_set.all(),
                source_tables,
                source_views,
                custom_queries,
            ),
            key=lambda x: x.name,
        )

        DataLinkWithLinkToggle = namedtuple(
            'DataLinkWithLinkToggle', ('data_link', 'can_show_link')
        )
        data_links_with_link_toggle = [
            DataLinkWithLinkToggle(
                data_link=data_link,
                can_show_link=data_link.can_show_link_for_user(self.request.user),
            )
            for data_link in data_links
        ]

        quicksight_dashboard_id = self.request.GET.get("quicksight_dashboard_id", None)
        if quicksight_dashboard_id:
            _, dashboard_url = get_quicksight_dashboard_name_url(
                quicksight_dashboard_id, self.request.user
            )
        else:
            _, dashboard_url = None, None

        ctx.update(
            {
                'has_access': self.object.user_has_access(self.request.user),
                'data_links_with_link_toggle': data_links_with_link_toggle,
                'fields': columns,
                'data_hosted_externally': any(
                    not source_link.url.startswith('s3://')
                    for source_link in self.object.sourcelink_set.all()
                ),
                'code_snippets': get_code_snippets(self.object),
                'visualisation_src': dashboard_url,
                'custom_dataset_query_type': DataLinkType.CUSTOM_QUERY.value,
                'source_table_type': DataLinkType.SOURCE_TABLE.value,
            }
        )
        return ctx

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
                field_name = field.name
                value = getattr(record, field.column_name)
                # If this is a linked field display the display name and id of that linked record
                if field.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    record_data[get_linked_field_identifier_name(field)] = (
                        value.get_identifier() if value is not None else None
                    )
                    record_data[get_linked_field_display_name(field)] = (
                        value.get_display_name() if value is not None else None
                    )
                else:
                    record_data[field_name] = value
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
            file_object['Body'].iter_chunks(), content_type=file_object['ContentType']
        )
        response[
            'Content-Disposition'
        ] = f'attachment; filename="{source_link.get_filename()}"'

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
