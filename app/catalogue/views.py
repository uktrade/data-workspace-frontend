import logging

from django.views.decorators.http import (
    require_GET,
)
from django.shortcuts import (
    render,
    get_object_or_404,
)

from catalogue.models import (
    DataGrouping,
    DataSet,
)

inline_edit = True

logger = logging.getLogger(__name__)


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    logger.info(f'looking for dataset {group_slug}/{set_slug}')
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)[0]

    context = {
        'inline_edit': inline_edit,
        'model': found,
        'links': found.datalink_set.all().order_by('name')
    }

    return render(request, 'dataset.html', context)


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
def datagroup_view(request):
    context = {
        'groupings': get_all_datagroups_viewmodel()
    }

    return render(request, 'catalogue.html', context)


@require_GET
def datagroup_item_view(request, slug):
    item = get_object_or_404(DataGrouping, slug=slug)

    context = {
        'inline_edit': inline_edit,
        'model': item,
        'datasets': item.dataset_set.all().order_by('name')
    }

    return render(request, 'datagroup.html', context)


@require_GET
def dataset_item_view(request, dataset_id):
    item = get_object_or_404(DataSet, pk=dataset_id)

    context = {
        'inline_edit': inline_edit,
        'model': item
    }

    return render(request, 'dataset.html', context)
