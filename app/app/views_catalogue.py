import csv
import json
import logging
import io
from contextlib import closing

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from django.urls import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, \
    StreamingHttpResponse, HttpResponseServerError
from django.shortcuts import (
    render,
    get_object_or_404,
)

from django.views.decorators.http import (
    require_GET,
    require_http_methods,
)
from django.views.generic import DetailView
from django.views.generic.base import View

from app.forms import RequestAccessForm
from app.models import (
    DataGrouping,
    DataSet,
    ReferenceDataset
)

from app.zendesk import create_zendesk_ticket

logger = logging.getLogger('app')


def get_all_datagroups_viewmodel():
    groupings = DataGrouping.objects.all().order_by('name')

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


@require_http_methods(['GET', 'POST'])
def request_access_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    if request.method == 'POST':
        form = RequestAccessForm(request.POST)
        if form.is_valid():
            justification = form.cleaned_data['justification']
            contact_email = form.cleaned_data['email']
            team_name = form.cleaned_data['team']

            user_edit_relative = reverse('admin:auth_user_change', args=[request.user.id])
            user_url = request.build_absolute_uri(user_edit_relative)

            dataset_name = f'{dataset.grouping.name} > {dataset.name}'

            dataset_url = request.build_absolute_uri(reverse('dataset_fullpath', args=[group_slug, set_slug]))

            ticket_reference = create_zendesk_ticket(contact_email,
                                                     request.user,
                                                     team_name,
                                                     justification,
                                                     user_url,
                                                     dataset_name,
                                                     dataset_url,
                                                     dataset.grouping.information_asset_owner,
                                                     dataset.grouping.information_asset_manager)

            url = reverse('request_access_success')
            return HttpResponseRedirect(
                f'{url}?ticket={ticket_reference}&group={group_slug}&set={set_slug}'
            )

    return render(request, 'request_access.html', {
        'dataset': dataset,
        'authenticated_user': request.user
    })


def find_dataset(group_slug, set_slug):
    return get_object_or_404(
        DataSet,
        grouping__slug=group_slug,
        slug=set_slug,
        published=True
    )


@require_GET
def request_access_success_view(request):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']
    group_slug = request.GET['group']
    set_slug = request.GET['set']

    dataset = find_dataset(group_slug, set_slug)

    return render(request, 'request_access_success.html', {
        'ticket': ticket,
        'dataset': dataset,
    })


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
        response['Content-Disposition'] = 'attachment; filename={}.{}'.format(
            ref_dataset.slug,
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


class SourceLinkDownloadView(View):
    def get(self, request, *args, **kwargs):
        filename = request.GET.get('f')
        if filename is None:
            raise Http404

        dataset = find_dataset(kwargs['group_slug'], kwargs['set_slug'])
        if not dataset.user_has_access(request.user):
            return HttpResponseForbidden()

        client = boto3.client('s3')
        try:
            file_object = client.get_object(
                Bucket=settings.AWS_UPLOADS_BUCKET,
                Key=filename
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
            filename
        )
        return response
