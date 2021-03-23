import logging
from urllib.parse import quote

from django.conf import settings
from django.db import connections
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
def search_in_data_explorer(request, schema, table):
    q = request.GET.get("q")

    with connections[settings.DATASET_FINDER_DB_NAME].cursor() as cursor:
        cursor.execute(
            """
            SELECT attname AS column, atttypid::regtype AS datatype
            FROM pg_attribute
            WHERE attrelid = %s::regclass
            AND attnum > 0
            AND NOT attisdropped
            AND atttypid::regtype IN ('text', 'text[]', 'json', 'character varying', 'character varying[]')
            ORDER BY attnum;""",
            [f'"{schema}"."{table}"'],
        )

        tsvector_fragments = []
        for column, datatype in cursor.fetchall():
            if datatype in ('text[]', 'character varying[]'):
                tsvector_fragments.append(f"array_to_string(\"{column}\", ', ')")
            elif datatype == "json":
                tsvector_fragments.append(f'"{column}"::text')
            else:
                tsvector_fragments.append(f'"{column}"')

    tsvector_fragment = ", ".join(tsvector_fragments)
    phrase_fragment = " <-> ".join(q.split(" "))

    condition = f"to_tsvector(concat_ws(',', {tsvector_fragment})) @@ to_tsquery('{phrase_fragment}')"

    query = f"""SELECT *
FROM "{schema}"."{table}"
WHERE {condition}"""

    return HttpResponseRedirect(f"{reverse('explorer:index')}?sql={quote(query)}")
