import logging

from django.db import (
    connections
)
from django import forms

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import (
    render,
    get_object_or_404,
)

from django.views.decorators.http import (
    require_GET,
    require_http_methods)

from app.models import (
    DataGrouping,
    DataSet,
    DataSetUserPermission)
from app.shared import (
    can_access_schema,
    tables_in_schema,
    can_access_dataset)

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
        'datasets': item.dataset_set.all().order_by('name')
    }

    return render(request, 'datagroup.html', context)


class RequestAccessForm(forms.Form):
    justification = forms.Textarea()


@require_http_methods(["GET", "POST"])
def dataset_full_path_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)
    form = RequestAccessForm()
    messages = []
    if request.method == 'POST':
        form = RequestAccessForm(request.POST)
        if form.is_valid():

            # OBVIOUSLY THIS IS A MASSIVE HACK AND A WORK IN PROGRESS
            perm = DataSetUserPermission()
            perm.user = request.user
            perm.dataset = dataset

            perm.save()

            # Send the request to zendesk
            messages.append("Thank you so very much for requesting access\n Your case reference is abcdefg")


    return dataset_full_path_view_get(request, dataset, form, messages)


def find_dataset(group_slug, set_slug):
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)

    if not found:
        raise Http404

    dataset = found[0]
    return dataset


def dataset_full_path_view_get(request, dataset, form, messages):
    schemas = dataset.sourceschema_set.all().order_by('schema', 'database__memorable_name', 'database__id')

    can_access_schemas = {
        (schema.database.memorable_name, schema.schema):
            can_access_schema(request.user, schema.database.memorable_name, schema.schema)
        for schema in schemas
    }

    # Could be more efficient if we have multiple schemas in the same db
    # but we only really expect the one schema anyway
    def connect_and_tables_in_schema(schema):
        with connections[schema.database.memorable_name].cursor() as cur:
            return tables_in_schema(cur, schema.schema)

    database_schema_table_accesses = [
        (
            schema.database.memorable_name,
            schema.schema,
            table,
            can_access_schemas[(schema.database.memorable_name, schema.schema)],
        )
        for schema in schemas
        for table in connect_and_tables_in_schema(schema)
    ]

    must_request_download_access = not dataset.datasetuserpermission_set.filter(user=request.user).exists()

    context = {
        'model': dataset,
        'form': form,
        'must_request_download_access': must_request_download_access,
        'links': dataset.sourcelink_set.all().order_by('name'),
        'database_schema_table_accesses': database_schema_table_accesses,
    }

    if messages:
        context['messages'] = messages

    return render(request, 'dataset.html', context)
