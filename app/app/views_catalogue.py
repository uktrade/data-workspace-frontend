import logging

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
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)[0]

    context = {
        'model': found,
        'links': found.sourcelink_set.all().order_by('name')
    }

    return render(request, 'dataset.html', context)
