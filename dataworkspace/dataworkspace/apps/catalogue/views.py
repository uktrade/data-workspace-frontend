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
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F
from django.db.models.functions import Lower
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
from django.views.decorators.http import require_GET
from django.views.generic import DetailView
from psycopg2 import sql

from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from dataworkspace.apps.core.utils import (
    table_data,
    view_exists,
    streaming_query_response,
)
from dataworkspace.apps.datasets.models import (
    DataGrouping,
    ReferenceDataset,
    SourceLink,
    ReferenceDatasetField,
    CustomDatasetQuery,
    SourceView,
)
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.model_utils import (
    get_linked_field_display_name,
    get_linked_field_identifier_name,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event

logger = logging.getLogger('app')


@require_GET
def datagroup_item_view(request, slug):
    item = get_object_or_404(DataGrouping.objects.with_published_datasets(), slug=slug)

    context = {
        'model': item,
        'datasets': item.dataset_set.filter(published=True).order_by('name'),
        'reference_datasets': item.referencedataset_set.live()
        .filter(published=True)
        .exclude(is_joint_dataset=True)
        .order_by('name'),
        'joint_datasets': item.referencedataset_set.live()
        .filter(is_joint_dataset=True, published=True)
        .order_by('name'),
    }

    return render(request, 'datagroup.html', context)


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)
    return HttpResponseRedirect(dataset.get_absolute_url())


class ReferenceDatasetDetailView(DetailView):  # pylint: disable=too-many-ancestors
    model = ReferenceDataset

    def get_object(self, queryset=None):
        group = get_object_or_404(DataGrouping, slug=self.kwargs.get('group_slug'))
        return get_object_or_404(
            ReferenceDataset,
            published=True,
            deleted=False,
            group=group,
            slug=self.kwargs.get('reference_slug'),
        )

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(self.get_object().get_absolute_url())


class ReferenceDatasetDownloadView(ReferenceDatasetDetailView):
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
        dataset = find_dataset(
            self.kwargs.get('group_slug'), self.kwargs.get('set_slug')
        )

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
        dataset = find_dataset(
            self.kwargs.get('group_slug'), self.kwargs.get('set_slug')
        )
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
        dataset = find_dataset(
            self.kwargs.get('group_slug'), self.kwargs.get('set_slug')
        )

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


def root_view(request):
    return (
        root_view_GET(request) if request.method == 'GET' else HttpResponse(status=405)
    )


def root_view_GET(request):
    sso_id_hex = hashlib.sha256(
        str(request.user.profile.sso_id).encode('utf-8')
    ).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in filter_api_visible_application_instances_by_owner(
            request.user
        )
    }

    def link(application_template):
        # Not the most robust method of finding the hostname, but the patterns aren't ever
        # directly controlled by users.
        public_host = application_template.host_pattern
        public_host = public_host.replace('^', '')
        public_host = public_host.replace('$', '')
        # Some patterns have "<user>", but some have "(?P<user>.*)"
        public_host = public_host.replace('(?P<user>.*)', '<user>')
        public_host = public_host.replace('<user>', sso_id_hex_short)

        return f'{request.scheme}://{public_host}.{settings.APPLICATION_ROOT_DOMAIN}/'

    context = {
        'applications': [
            {
                'name': application_template.name,
                'nice_name': application_template.nice_name,
                'link': link(application_template),
                'instance': application_instances.get(application_template, None),
            }
            for application_template in ApplicationTemplate.objects.all().order_by(
                'name'
            )
            for application_link in [link(application_template)]
            if application_template.visible
        ],
        'appstream_url': settings.APPSTREAM_URL,
        'your_files_enabled': settings.YOUR_FILES_ENABLED,
        'groupings': DataGrouping.objects.with_published_datasets().order_by(
            Lower('name')
        ),
    }
    return render(request, 'root.html', context)


def filter_api_visible_application_instances_by_owner(owner):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.filter(
        owner=owner, state__in=['RUNNING', 'SPAWNING']
    )


def _flatten(to_flatten):
    return [item for sub_list in to_flatten for item in sub_list]
