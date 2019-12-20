from itertools import chain

from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import DetailView

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.forms import RequestAccessForm, EligibilityCriteriaForm
from dataworkspace.apps.datasets.models import ReferenceDataset, DataSet
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
