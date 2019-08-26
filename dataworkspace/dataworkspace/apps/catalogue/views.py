import csv
import hashlib
import io
import json
import logging
import os

from contextlib import closing

import boto3
from botocore.exceptions import ClientError

from django.conf import settings
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.forms import model_to_dict
from django.http import (Http404, HttpResponse, HttpResponseForbidden,
                         StreamingHttpResponse, HttpResponseServerError, HttpResponseRedirect,
                         HttpResponseNotFound)
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationTemplate
from dataworkspace.apps.applications.utils import stop_spawner_and_application
from dataworkspace.apps.core.utils import table_exists, table_data
from dataworkspace.apps.datasets.models import DataGrouping, ReferenceDataset, SourceLink, \
    SourceTable
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event

logger = logging.getLogger('app')


def get_all_datagroups_viewmodel():
    groupings = DataGrouping.objects.live().order_by('name')

    vm = []

    for group in groupings:
        vm.append({
            'name': group.name,
            'short_description': group.short_description,
            'id': group.id,
            'slug': group.slug
        })

    return vm


@require_GET
def datagroup_item_view(request, slug):
    item = get_object_or_404(DataGrouping, slug=slug)

    context = {
        'model': item,
        'datasets': item.dataset_set.filter(published=True).order_by('name'),
        'reference_datasets': item.referencedataset_set.live().filter(
            published=True
        ).order_by('name'),
    }

    return render(request, 'datagroup.html', context)


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    context = {
        'model': dataset,
        'has_download_access': dataset.user_has_access(request.user),
        'links': dataset.sourcelink_set.all().order_by('name'),
        'tables': dataset.sourcetable_set.all().order_by(
            'schema', 'table', 'database__memorable_name', 'database__id'
        )
    }

    return render(request, 'dataset.html', context)


class ReferenceDatasetDetailView(DetailView):  # pylint: disable=too-many-ancestors
    model = ReferenceDataset

    def get_object(self, queryset=None):
        group = get_object_or_404(
            DataGrouping,
            slug=self.kwargs.get('group_slug')
        )
        return get_object_or_404(
            ReferenceDataset,
            published=True,
            deleted=False,
            group=group,
            slug=self.kwargs.get('reference_slug')
        )


class ReferenceDatasetDownloadView(ReferenceDatasetDetailView):
    def get(self, request, *args, **kwargs):
        dl_format = self.kwargs.get('format')
        if dl_format not in ['json', 'csv']:
            raise Http404
        ref_dataset = self.get_object()
        records = [
            {
                field.name: record[field.column_name]
                for field in ref_dataset.fields.all()
            }
            for record in ref_dataset.get_records().values(
                *ref_dataset.column_names
            )
        ]
        response = HttpResponse()
        response['Content-Disposition'] = 'attachment; filename={}-{}.{}'.format(
            ref_dataset.slug,
            ref_dataset.version,
            dl_format
        )

        log_event(
            request.user,
            EventLog.TYPE_REFERENCE_DATASET_DOWNLOAD,
            ref_dataset,
            extra={
                'path': request.get_full_path(),
                'reference_dataset_version': ref_dataset.version,
                'download_format': dl_format,
            }
        )

        if dl_format == 'json':
            response['Content-Type'] = 'application/json'
            response.write(json.dumps(list(records), cls=DjangoJSONEncoder))
        else:
            response['Content-Type'] = 'text/csv'
            with closing(io.StringIO()) as outfile:
                writer = csv.DictWriter(
                    outfile,
                    fieldnames=ref_dataset.field_names
                )
                writer.writeheader()
                writer.writerows(records)
                response.write(outfile.getvalue())  # pylint: disable=no-member
        return response


class SourceLinkDownloadView(DetailView):
    model = SourceLink

    def get(self, request, *args, **kwargs):
        dataset = find_dataset(
            self.kwargs.get('group_slug'),
            self.kwargs.get('set_slug')
        )

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        source_link = get_object_or_404(
            SourceLink,
            id=self.kwargs.get('source_link_id'),
            dataset=dataset
        )

        log_event(
            request.user,
            EventLog.TYPE_DATASET_SOURCE_LINK_DOWNLOAD,
            source_link.dataset,
            extra={
                'path': request.get_full_path(),
                **model_to_dict(source_link)
            }
        )

        if source_link.link_type == source_link.TYPE_EXTERNAL:
            return HttpResponseRedirect(source_link.url)

        client = boto3.client('s3')
        try:
            file_object = client.get_object(
                Bucket=settings.AWS_UPLOADS_BUCKET,
                Key=source_link.url
            )
        except ClientError as ex:
            try:
                return HttpResponse(
                    status=ex.response['ResponseMetadata']['HTTPStatusCode']
                )
            except KeyError:
                return HttpResponseServerError()

        response = StreamingHttpResponse(
            file_object['Body'].iter_chunks(),
            content_type=file_object['ContentType']
        )
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            os.path.split(source_link.url)[-1]
        )

        return response


class SourceTableDownloadView(DetailView):
    model = SourceTable

    def get(self, request, *args, **kwargs):
        dataset = find_dataset(
            self.kwargs.get('group_slug'),
            self.kwargs.get('set_slug')
        )

        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        table = get_object_or_404(
            SourceTable,
            id=self.kwargs.get('source_table_id'),
            dataset=dataset
        )

        if not table_exists(table.database.memorable_name, table.schema, table.table):
            return HttpResponseNotFound()

        log_event(
            request.user,
            EventLog.TYPE_DATASET_SOURCE_TABLE_DOWNLOAD,
            table.dataset,
            extra={
                'path': request.get_full_path(),
                **model_to_dict(table)
            }
        )

        return table_data(request.user.email, table.database.memorable_name, table.schema, table.table)


def root_view(request):
    return \
        root_view_GET(request) if request.method == 'GET' else \
        root_view_POST(request) if request.method == 'POST' else \
        HttpResponse(status=405)


def root_view_GET(request):
    sso_id_hex = hashlib.sha256(str(request.user.profile.sso_id).encode('utf-8')).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in filter_api_visible_application_instances_by_owner(request.user)
    }

    def link(application_template):
        public_host = application_template.host_pattern.replace('<user>', sso_id_hex_short)
        return f'{request.scheme}://{public_host}.{settings.APPLICATION_ROOT_DOMAIN}/'

    context = {
        'applications': [
            {
                'name': application_template.name,
                'nice_name': application_template.nice_name,
                'link': link(application_template),
                'instance': application_instances.get(application_template, None),
            }
            for application_template in ApplicationTemplate.objects.all().order_by('name')
        ],
        'appstream_url': settings.APPSTREAM_URL,
        'groupings': get_all_datagroups_viewmodel()
    }
    return render(request, 'root.html', context)


def root_view_POST(request):
    public_host = request.POST['public_host']
    try:
        application_instance = ApplicationInstance.objects.get(
            owner=request.user,
            public_host=public_host,
            state__in=['RUNNING', 'SPAWNING'],
        )
    except ApplicationInstance.DoesNotExist:
        # The user could force a POST for any public_host, and will be able to
        # get the server to show this message, but this is acceptable since it
        # won't cause any harm
        messages.success(request, application_instance.application_template.nice_name + ' was already stopped')
    else:
        stop_spawner_and_application(application_instance)
        messages.success(request, 'Stopped ' + application_instance.application_template.nice_name)
    return redirect('root')


def filter_api_visible_application_instances_by_owner(owner):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.filter(owner=owner, state__in=['RUNNING', 'SPAWNING'])


def _flatten(to_flatten):
    return [
        item
        for sub_list in to_flatten
        for item in sub_list
    ]
