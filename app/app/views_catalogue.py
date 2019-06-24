import logging

from django.db import (
    connections
)
from django.http import Http404
from django.shortcuts import (
    render,
    get_object_or_404,
)

from django.views.decorators.http import (
    require_GET,
)

from app.models import (
    DataGrouping,
    DataSet,
)
from app.shared import (
    tables_in_schema,
)

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


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)

    if not found:
        raise Http404

    dataset = found[0]
    schemas = dataset.sourceschema_set.all().order_by('schema', 'database__memorable_name', 'database__id')

    # Could be more efficient if we have multiple schemas in the same db
    # but we only really expect the one schema anyway
    def connect_and_tables_in_schema(schema):
        with connections[schema.database.memorable_name].cursor() as cur:
            return tables_in_schema(cur, schema.schema)

    database_schema_tables = [
        (schema.database.memorable_name, schema.schema, table)
        for schema in schemas
        for table in connect_and_tables_in_schema(schema)
    ]

    context = {
        'model': dataset,
        'links': dataset.sourcelink_set.all().order_by('name'),
        'database_schema_tables': database_schema_tables,
    }

    return render(request, 'dataset.html', context)
