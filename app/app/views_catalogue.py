import logging

from django.db import (
    connections
)
from django import forms

from django.urls import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import (
    render,
    get_object_or_404,
)

from django.views.decorators.http import (
    require_GET,
    require_http_methods,
)

from app.models import (
    DataGrouping,
    DataSet,
)

from app.shared import (
    tables_in_schema,
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
        'datasets': item.dataset_set.all().order_by('name')
    }

    return render(request, 'datagroup.html', context)


class RequestAccessForm(forms.Form):
    email = forms.CharField(widget=forms.TextInput, required=True)
    justification = forms.CharField(widget=forms.Textarea, required=True)
    team = forms.CharField(widget=forms.TextInput, required=True)


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
                f'{url}?ticket={ticket_reference}&group={group_slug}&set={set_slug}&email={contact_email}')

    return render(request, 'request_access.html', {
        'dataset': dataset,
        'authenticated_user': request.user
    })


def find_dataset(group_slug, set_slug):
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)

    if not found:
        raise Http404

    dataset = found[0]
    return dataset


@require_GET
def request_access_success_view(request):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']
    group_slug = request.GET['group']
    set_slug = request.GET['set']
    email = request.GET['email']

    dataset = find_dataset(group_slug, set_slug)

    return render(request, 'request_access_success.html', {
        'ticket': ticket,
        'dataset': dataset,
        'confirmation_email': email,
    })


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    schemas = dataset.sourceschema_set.all().order_by('schema', 'database__memorable_name', 'database__id')
    tables = dataset.sourcetable_set.all().order_by('schema', 'table', 'database__memorable_name', 'database__id')

    # Could be more efficient if we have multiple schemas in the same db
    # but we only really expect the one schema anyway
    def connect_and_tables_in_schema(schema):
        with connections[schema.database.memorable_name].cursor() as cur:
            return tables_in_schema(cur, schema.schema)

    database_schema_table_name = [
        (
            schema.database.memorable_name,
            schema.schema,
            table,
            f'{schema.schema} / {table}'
        )
        for schema in schemas
        for table in connect_and_tables_in_schema(schema)
    ] + [
        (
            table.database.memorable_name,
            table.schema,
            table.table,
            table.name
        )
        for table in tables
    ]

    has_download_access = \
        dataset.user_access_type == 'REQUIRES_AUTHENTICATION' or \
        dataset.datasetuserpermission_set.filter(user=request.user).exists()

    context = {
        'model': dataset,
        'has_download_access': has_download_access,
        'links': dataset.sourcelink_set.all().order_by('name'),
        'database_schema_table_name': database_schema_table_name,
    }

    return render(request, 'dataset.html', context)
