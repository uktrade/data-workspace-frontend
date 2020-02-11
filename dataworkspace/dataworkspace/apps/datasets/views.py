import csv
import io
import json
import os
from contextlib import closing
from itertools import chain

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F
from django.forms import model_to_dict
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    StreamingHttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
    HttpResponseNotFound,
)
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import DetailView
from psycopg2 import sql

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.forms import (
    DatasetSearchForm,
    RequestAccessForm,
    EligibilityCriteriaForm,
)
from dataworkspace.apps.datasets.models import (
    DataSet,
    ReferenceDataset,
    SourceLink,
    ReferenceDatasetField,
    CustomDatasetQuery,
    SourceView,
)
from dataworkspace.apps.datasets.model_utils import (
    get_linked_field_display_name,
    get_linked_field_identifier_name,
)
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.core.utils import (
    table_data,
    view_exists,
    streaming_query_response,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.zendesk import create_zendesk_ticket


def filter_datasets(datasets, query, source, use=None):
    search = SearchVector('name', 'short_description', config='english')
    search_query = SearchQuery(query, config='english')

    datasets = datasets.filter(published=True).annotate(
        search=search, search_rank=SearchRank(search, search_query)
    )

    if query:
        datasets = datasets.filter(search=query)

    if source:
        datasets = datasets.filter(source_tags__in=source)

    if use:
        datasets = datasets.filter(type__in=use)

    return datasets


@require_GET
def find_datasets(request):
    form = DatasetSearchForm(request.GET)

    if form.is_valid():
        query = form.cleaned_data.get("q")
        use = form.cleaned_data.get("use")
        source = form.cleaned_data.get("source")
    else:
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    datasets = filter_datasets(DataSet.objects, query, source, use)

    # Include reference datasets if required
    if not use or "0" in use:
        reference_datasets = filter_datasets(
            ReferenceDataset.objects.live(), query, source
        )
        datasets = datasets.values(
            'id', 'name', 'slug', 'short_description', 'search_rank'
        ).union(
            reference_datasets.values(
                'uuid', 'name', 'slug', 'short_description', 'search_rank'
            )
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
        },
    )


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def get_object(self, queryset=None):
        try:
            return ReferenceDataset.objects.live().get(
                uuid=self.kwargs['dataset_uuid'], published=True
            )
        except ReferenceDataset.DoesNotExist:
            pass

        return get_object_or_404(
            DataSet, published=True, id=self.kwargs['dataset_uuid']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        if self._is_reference_dataset():
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

        ctx.update(
            {
                'model': self.object,
                'has_access': self.object.user_has_access(self.request.user),
                'data_links': sorted(
                    chain(
                        self.object.sourcelink_set.all(),
                        source_tables,
                        source_views,
                        custom_queries,
                    ),
                    key=lambda x: x.name,
                ),
                'fields': columns,
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


@require_http_methods(['GET', 'POST'])
def eligibility_criteria_view(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid)

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
    dataset = find_dataset(dataset_uuid)

    return render(request, 'eligibility_criteria_not_met.html', {'dataset': dataset})


@require_http_methods(['GET', 'POST'])
def request_access_view(request, dataset_uuid):
    dataset = find_dataset(dataset_uuid)

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

            url = reverse('datasets:request_access_success', args=[dataset_uuid])
            return HttpResponseRedirect(
                f'{url}?ticket={ticket_reference}&set={dataset_uuid}'
            )

    return render(
        request,
        'request_access.html',
        {'dataset': dataset, 'authenticated_user': request.user},
    )


@require_GET
def request_access_success_view(request, dataset_uuid):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']
    dataset_uuid = request.GET['set']

    dataset = find_dataset(dataset_uuid)

    return render(
        request, 'request_access_success.html', {'ticket': ticket, 'dataset': dataset}
    )


class ReferenceDatasetDownloadView(DetailView):
    model = ReferenceDataset

    def get_object(self, queryset=None):
        return get_object_or_404(
            ReferenceDataset,
            published=True,
            deleted=False,
            uuid=self.kwargs.get('dataset_uuid'),
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
        dataset = find_dataset(self.kwargs.get('dataset_uuid'))

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        source_link = get_object_or_404(
            SourceLink, id=self.kwargs.get('source_link_id'), dataset=dataset
        )

        log_event(
            request.user,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
            source_link.dataset,
            extra={'path': request.get_full_path(), **model_to_dict(source_link)},
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

        response = StreamingHttpResponse(
            file_object['Body'].iter_chunks(), content_type=file_object['ContentType']
        )
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            os.path.split(source_link.url)[-1]
        )

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
        dataset = find_dataset(self.kwargs.get('dataset_uuid'))
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
            extra={'path': request.get_full_path(), **model_to_dict(db_object)},
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
        )


class CustomDatasetQueryDownloadView(DetailView):
    model = CustomDatasetQuery

    def get(self, request, *args, **kwargs):
        dataset = find_dataset(self.kwargs.get('dataset_uuid'))

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        query = get_object_or_404(
            self.model, id=self.kwargs.get('query_id'), dataset=dataset
        )

        log_event(
            request.user,
            EventLog.TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD,
            query.dataset,
            extra={'path': request.get_full_path(), **model_to_dict(query)},
        )
        dataset.number_of_downloads = F('number_of_downloads') + 1
        dataset.save(update_fields=['number_of_downloads'])

        return streaming_query_response(
            request.user.email,
            query.database.memorable_name,
            sql.SQL(query.query),
            query.get_filename(),
        )
