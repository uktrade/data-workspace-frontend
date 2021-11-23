import json
import logging

from django.conf import settings
from django.core.paginator import Paginator
from django.http import (
    Http404,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from waffle.decorators import waffle_flag
from waffle.mixins import WaffleFlagMixin

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.constants import GRID_DATA_TYPE_MAP
from dataworkspace.apps.datasets.models import SourceTable
from dataworkspace.apps.finder.elasticsearch import es_client
from dataworkspace.apps.finder.forms import DatasetFindForm
from dataworkspace.apps.finder.utils import (
    build_grid_filters,
    group_tables_by_master_dataset,
    _enrich_and_suppress_matches,
    get_index_aliases_for_all_published_source_tables,
    log_query,
    ResultsProxy,
)


logger = logging.getLogger("app")


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
            visible_matches, has_suppressed_tables = _enrich_and_suppress_matches(request, matches)
            results = group_tables_by_master_dataset(visible_matches, request.user)

        if search_term:
            log_query(request.user, search_term)
    else:
        return HttpResponseRedirect(reverse("finder:find_datasets"))

    return render(
        request,
        "finder/index.html",
        {
            "form": form,
            "request": request,
            "search_term": search_term,
            "results": results,
            "has_hidden_tables": has_suppressed_tables,
        },
    )


class BaseResultsView(WaffleFlagMixin, DetailView):
    waffle_flag = settings.DATASET_FINDER_ADMIN_ONLY_FLAG

    def _user_can_access(self):
        return self.get_object().dataset.user_has_access(self.request.user)

    def _get_index_alias(self):
        return f'{self.kwargs["schema"]}--{self.kwargs["table"]}'

    def get_object(self, queryset=None):
        return get_object_or_404(
            SourceTable,
            dataset__deleted=False,
            dataset__published=True,
            dataset__id=self.request.GET.get("uuid"),
            schema=self.kwargs["schema"],
            table=self.kwargs["table"],
        )

    def _get_columns(self):
        """
        Return a list of columns in the datasets db for this source table
        """
        source_table = self.get_object()
        return datasets_db.get_columns(
            source_table.database.memorable_name,
            schema=source_table.schema,
            table=source_table.table,
            include_types=True,
        )

    def _get_column_config(self):
        """
        Return a list of column definitions for configuring ag-grid.
        Any fields present in the dataset but not in the es index are removed.
        """
        es_fields = es_client.get_fields(self._get_index_alias())

        filter_map = {
            "text": ["contains", "notContains"],
            "date": ["equals", "notEqual", "greaterThan", "lessThan", "inRange"],
            "numeric": ["equals", "greaterThan", "lessThan"],
            "boolean": ["equals"],
            "uuid": ["contains", "notContains"],
        }
        return [
            {
                "field": column[0],
                "filter": GRID_DATA_TYPE_MAP.get(column[1], "text") in filter_map,
                "sortable": False,
                "dataType": GRID_DATA_TYPE_MAP.get(column[1], "text"),
                "filterParams": {
                    "filterOptions": filter_map.get(GRID_DATA_TYPE_MAP.get(column[1], column[1]))
                },
            }
            for column in self._get_columns()
            if column[0] in es_fields
        ]

    def dispatch(self, request, *args, **kwargs):
        if not self._user_can_access():
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class ResultsView(BaseResultsView):
    template_name = "finder/results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        search_term = self.request.GET.get("q")

        ctx.update(
            {
                "search_term": search_term,
                "backlink": f'{reverse("finder:find_datasets")}?q={search_term}',
                "dataset": self.object.dataset,
                "source_table": self.object,
                "columns": self._get_columns(),
                "total_results": es_client.get_count(search_term, self._get_index_alias()),
                "grid_column_definitions": self._get_column_config(),
            }
        )
        return ctx


class DataGridResultsView(BaseResultsView):
    def get(self, request, *args, **kwargs):
        raise Http404

    def post(self, request, *args, **kwargs):
        search_term = request.GET.get("q")
        post_data = json.loads(request.body.decode("utf-8"))
        start = int(post_data.get("start", 0))
        limit = int(post_data.get("limit", 100))

        filters = build_grid_filters(self._get_column_config(), post_data.get("filters", {}))

        result_count = es_client.get_count(search_term, self._get_index_alias(), filters=filters)

        results_proxy = ResultsProxy(
            es_client=es_client,
            index_alias=self._get_index_alias(),
            phrase=search_term,
            count=result_count,
            filters=filters,
        )
        paginator = Paginator(results_proxy, limit)
        results = paginator.get_page(1 if start <= 0 else int(start / limit) + 1)
        records = []
        if len(results) > 0 and "_source" in results[0]:
            records = [result["_source"] for result in results]

        return JsonResponse({"total": result_count, "records": records})
