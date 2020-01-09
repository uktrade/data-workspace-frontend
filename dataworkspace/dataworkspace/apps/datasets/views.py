from itertools import chain

from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import DetailView
from waffle.decorators import waffle_flag

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.forms import (
    DatasetSearchForm,
    RequestAccessForm,
    EligibilityCriteriaForm,
)
from dataworkspace.apps.datasets.models import DataSet, ReferenceDataset
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.zendesk import create_zendesk_ticket


@require_http_methods(['GET', 'POST'])
def eligibility_criteria_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    if request.method == 'POST':
        form = EligibilityCriteriaForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['meet_criteria']:
                return HttpResponseRedirect(
                    reverse('datasets:request_access', args=[group_slug, set_slug])
                )
            else:
                return HttpResponseRedirect(
                    reverse(
                        'datasets:eligibility_criteria_not_met',
                        args=[group_slug, set_slug],
                    )
                )

    return render(request, 'eligibility_criteria.html', {'dataset': dataset})


@require_GET
def eligibility_criteria_not_met_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    return render(request, 'eligibility_criteria_not_met.html', {'dataset': dataset})


@require_http_methods(['GET', 'POST'])
def request_access_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    if request.method == 'POST':
        form = RequestAccessForm(request.POST)
        if form.is_valid():
            goal = form.cleaned_data['goal']
            justification = form.cleaned_data['justification']
            contact_email = form.cleaned_data['email']

            user_edit_relative = reverse(
                'admin:auth_user_change', args=[request.user.id]
            )
            user_url = request.build_absolute_uri(user_edit_relative)

            dataset_name = f'{dataset.grouping.name} > {dataset.name}'

            dataset_url = request.build_absolute_uri(dataset.get_absolute_url())

            ticket_reference = create_zendesk_ticket(
                contact_email,
                request.user,
                goal,
                justification,
                user_url,
                dataset_name,
                dataset_url,
                dataset.grouping.information_asset_owner,
                dataset.grouping.information_asset_manager,
            )

            url = reverse('datasets:request_access_success')
            return HttpResponseRedirect(
                f'{url}?ticket={ticket_reference}&group={group_slug}&set={set_slug}'
            )

    return render(
        request,
        'request_access.html',
        {'dataset': dataset, 'authenticated_user': request.user},
    )


@require_GET
def request_access_success_view(request):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']
    group_slug = request.GET['group']
    set_slug = request.GET['set']

    dataset = find_dataset(group_slug, set_slug)

    return render(
        request, 'request_access_success.html', {'ticket': ticket, 'dataset': dataset}
    )


class DatasetDetailView(DetailView):
    def _is_reference_dataset(self):
        return isinstance(self.object, ReferenceDataset)

    def get_object(self, queryset=None):
        try:
            return ReferenceDataset.objects.live().get(
                uuid=self.kwargs['dataset_uuid'], published=True
            )
        except ReferenceDataset.DoesNotExist:
            pass

        return get_object_or_404(
            DataSet, published=True, id=self.kwargs['dataset_uuid']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        if self._is_reference_dataset():
            return ctx

        source_tables = sorted(self.object.sourcetable_set.all(), key=lambda x: x.name)
        source_views = self.object.sourceview_set.all()
        custom_queries = self.object.customdatasetquery_set.all()

        if source_tables:
            columns = []
            for table in source_tables:
                columns += [
                    "{}.{}".format(table.table, column)
                    for column in datasets_db.get_columns(
                        table.database.memorable_name,
                        schema=table.schema,
                        table=table.table,
                    )
                ]
        elif source_views:
            columns = datasets_db.get_columns(
                source_views[0].database.memorable_name,
                schema=source_views[0].schema,
                table=source_views[0].view,
            )
        elif custom_queries:
            columns = datasets_db.get_columns(
                custom_queries[0].database.memorable_name, query=custom_queries[0].query
            )
        else:
            columns = None

        ctx.update(
            {
                'model': self.object,
                'has_access': self.object.user_has_access(self.request.user),
                'data_links': sorted(
                    chain(
                        self.object.sourcelink_set.all(),
                        source_tables,
                        source_views,
                        custom_queries,
                    ),
                    key=lambda x: x.name,
                ),
                'fields': columns,
            }
        )
        return ctx

    def get_template_names(self):
        if self._is_reference_dataset():
            return ['datasets/referencedataset_detail.html']
        elif self.object.type == DataSet.TYPE_MASTER_DATASET:
            return ['datasets/master_dataset.html']
        elif self.object.type == DataSet.TYPE_DATA_CUT:
            return ['datasets/data_cut_dataset.html']


def filter_datasets(datasets, query, source, use=None):
    search = SearchVector('name', 'short_description')
    search_query = SearchQuery(query)

    datasets = datasets.annotate(
        search=search, search_rank=SearchRank(search, search_query)
    )

    if query:
        datasets = datasets.filter(search=query)

    if source:
        datasets = datasets.filter(source_tags__in=source)

    if use:
        datasets = datasets.filter(type__in=use)

    return datasets


@require_GET
@waffle_flag('datasets-search')
def find_datasets(request):
    form = DatasetSearchForm(request.GET)

    if form.is_valid():
        query = form.cleaned_data.get("q")
        use = form.cleaned_data.get("use")
        source = form.cleaned_data.get("source")
    else:
        return HttpResponseRedirect(reverse("datasets:find_datasets"))

    datasets = filter_datasets(DataSet.objects, query, source, use)

    # Include reference datasets if required
    if not use or "0" in use:
        reference_datasets = filter_datasets(ReferenceDataset.objects, query, source)
        datasets = datasets.values(
            'id', 'name', 'short_description', 'search_rank'
        ).union(
            reference_datasets.values(
                'uuid', 'name', 'short_description', 'search_rank'
            )
        )

    paginator = Paginator(
        datasets.order_by('-search_rank', 'name'),
        settings.SEARCH_RESULTS_DATASETS_PER_PAGE,
    )

    return render(
        request,
        'datasets/index.html',
        {
            "form": form,
            "query": query,
            "datasets": paginator.get_page(request.GET.get("page")),
        },
    )
