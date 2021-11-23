import logging

from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from dataworkspace.apps.datasets.models import DataSet, ReferenceDataset

logger = logging.getLogger("app")


@require_GET
def datagroup_item_view(request, slug):
    GROUP_TO_SEARCH_QUERY = {
        "data-hub-companies": {"q": "Data Hub companies"},
        "data-hub-contacts": {"q": "Data Hub contacts"},
        "data-hub-interactions-service-deliveries": {"q": "Data Hub interactions"},
        "data-hub-investment-projects": {"q": "Data Hub investment projects"},
        "export-wins": {"q": "Export Wins"},
        "one-list": {"q": "One List"},
        "reference-data-sets": {"use": "0"},
    }

    search_params = QueryDict("", mutable=True)
    search_params.update(GROUP_TO_SEARCH_QUERY.get(slug, {}))

    return HttpResponseRedirect(
        reverse("datasets:find_datasets") + "?" + search_params.urlencode()
    )


@require_GET
def dataset_full_path_view(request, group_slug, set_slug):
    dataset = get_object_or_404(
        DataSet.objects.live(), grouping__slug=group_slug, slug=set_slug, published=True
    )
    return HttpResponseRedirect(dataset.get_absolute_url())


class ReferenceDatasetDetailView(DetailView):  # pylint: disable=too-many-ancestors
    model = ReferenceDataset

    def get_object(self, queryset=None):
        return get_object_or_404(
            ReferenceDataset.objects.live(),
            published=True,
            group__slug=self.kwargs.get("group_slug"),
            slug=self.kwargs.get("reference_slug"),
        )

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(self.get_object().get_absolute_url())
