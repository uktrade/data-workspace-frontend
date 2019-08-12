import boto3
import csv
import hashlib
import io
import json
import logging
import os

from botocore.exceptions import ClientError
from contextlib import closing

from django.conf import settings
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.http import (Http404, HttpResponse, HttpResponseForbidden,
                         StreamingHttpResponse, HttpResponseServerError, HttpResponseRedirect)
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationTemplate
from dataworkspace.apps.applications.spawner import get_spawner
from dataworkspace.apps.core.utils import stop_spawner_and_application
from dataworkspace.apps.datasets.models import DataGrouping, ReferenceDataset, SourceLink
from dataworkspace.apps.datasets.utils import find_dataset

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

    tables = dataset.sourcetable_set.all().order_by('schema', 'table', 'database__memorable_name', 'database__id')
    database_schema_table_name = [
        (
            table.database.memorable_name,
            table.schema,
            table.table,
            table.name
        )
        for table in tables
    ]

    context = {
        'model': dataset,
        'has_download_access': dataset.user_has_access(request.user),
        'links': dataset.sourcelink_set.all().order_by('name'),
        'database_schema_table_name': database_schema_table_name,
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


class ReferenceDatasetDownloadView(ReferenceDatasetDetailView):  # pylint: disable=too-many-ancestors
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


class SourceLinkDownloadView(DetailView):  # pylint: disable=too-many-ancestors
    model = SourceLink

    def get_object(self, queryset=None):
        dataset = find_dataset(
            self.kwargs.get('group_slug'),
            self.kwargs.get('set_slug')
        )
        if not dataset.user_has_access(self.request.user):
            return HttpResponseForbidden()

        return get_object_or_404(
            SourceLink,
            id=self.kwargs.get('source_link_id'),
            dataset=dataset
        )

    def get(self, request, *args, **kwargs):
        source_link = self.get_object()
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

    def can_stop(application_template):
        application_instance = application_instances.get(application_template, None)
        return \
            application_instance is not None and get_spawner(application_instance.spawner).can_stop(
                application_instance.spawner_application_template_options,
                application_instance.spawner_application_instance_id,
            )

    context = {
        'applications': [
            {
                'name': application_template.name,
                'nice_name': application_template.nice_name,
                'link': f'{request.scheme}://{application_template.name}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/',
                'instance': application_instances.get(application_template, None),
                'can_stop': can_stop(application_template),
            }
            for application_template in ApplicationTemplate.objects.all().order_by('name')
        ],
        'appstream_url': settings.APPSTREAM_URL,
        'groupings': get_all_datagroups_viewmodel()
    }
    return render(request, 'root.html', context)


def root_view_POST(request):
    application_instance_id = request.POST['application_instance_id']
    application_instance = ApplicationInstance.objects.get(
        id=application_instance_id,
        owner=request.user,
        state__in=['RUNNING', 'SPAWNING'],
    )

    if application_instance.state != 'STOPPED':
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
