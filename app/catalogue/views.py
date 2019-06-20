import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.http import (
    require_GET,
)
from django.shortcuts import (
    render,
    get_object_or_404,
)

from .forms import (
    ContactForm
)

from catalogue.models import (
    DataGrouping,
    DataSet,
)

logger = logging.getLogger(__name__)


def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            return render(request, 'contact_thankyou.html', {'form': form})

    else:
        form = ContactForm()

    return render(request, 'contact.html', {'form': form})


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    logger.info(f'looking for dataset {group_slug}/{set_slug}')
    found = DataSet.objects.filter(grouping__slug=group_slug, slug=set_slug)[0]

    context = {
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
        'model': item,
        'datasets': item.dataset_set.all().order_by('name')
    }

    return render(request, 'datagroup.html', context)


@require_GET
def dataset_item_view(request, dataset_id):
    item = get_object_or_404(DataSet, pk=dataset_id)

    context = {
        'model': item
    }

    return render(request, 'dataset.html', context)
