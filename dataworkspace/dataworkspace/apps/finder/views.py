import logging

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from waffle.decorators import waffle_flag

from dataworkspace.apps.finder.elasticsearch import es_client
from dataworkspace.apps.finder.forms import DatasetFindForm
from dataworkspace.apps.finder.utils import (
    group_tables_by_master_dataset,
    _enrich_and_suppress_matches,
    get_index_aliases_for_all_published_source_tables,
    log_query,
    ResultsProxy,
)


logger = logging.getLogger('app')


@waffle_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG)
@require_GET
def find_datasets(request):
    results = []
    has_suppressed_tables = False

    form = DatasetFindForm(request.GET)
    if form.is_valid():
        search_term = form.cleaned_data.get("q")
        index_aliases = get_index_aliases_for_all_published_source_tables()
        matches = (
            es_client.search_for_phrase(search_term, index_aliases=index_aliases)
            if search_term
            else None
        )
        if matches:
            visible_matches, has_suppressed_tables = _enrich_and_suppress_matches(
                request, matches
            )
            results = group_tables_by_master_dataset(visible_matches)

        if search_term:
            log_query(request.user, search_term)
    else:
        return HttpResponseRedirect(reverse("finder:find_datasets"))

    return render(
        request,
        'finder/index.html',
        {
            "form": form,
            "request": request,
            "search_term": search_term,
            "results": results,
            "has_hidden_tables": has_suppressed_tables,
        },
    )


@waffle_flag(settings.DATASET_FINDER_ADMIN_ONLY_FLAG)
@require_GET
def show_results(request, schema, table):
    search_term = request.GET.get("q")
    index_alias = f"{schema}--{table}"
    results_proxy = ResultsProxy(
        es_client=es_client,
        index_alias=index_alias,
        phrase=search_term,
        count=es_client.get_count(search_term, index_alias),
    )
    paginator = Paginator(
        results_proxy, settings.DATASET_FINDER_SEARCH_RESULTS_PER_PAGE
    )
    results = paginator.get_page(request.GET.get("page"))
    records = []
    fields = []
    if len(results) > 0 and "_source" in results[0]:
        records = [result['_source'] for result in results]
        fields = list(records[0].keys())
    return render(
        request,
        'finder/results.html',
        {
            "request": request,
            "schema": schema,
            "table": table,
            "search_term": search_term,
            "fields": fields,
            "records": records,
            "results": results,
            "backlink": f'{reverse("finder:find_datasets")}?q={search_term}',
        },
    )
