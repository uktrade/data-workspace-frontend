import operator
from dataclasses import dataclass
from functools import reduce
from typing import List, Iterable

from django.db.models import Q, Case, When, BooleanField, F, Value
from django.db.models.functions import Concat

from dataworkspace.apps.datasets.models import SourceTable
from dataworkspace.apps.finder.elasticsearch import _TableMatchResult
from dataworkspace.apps.finder.models import DatasetFinderQueryLog


@dataclass
class _DatasetMatch:
    id: str
    slug: str
    name: str
    table_matches: List[_TableMatchResult]

    @property
    def count(self):
        return sum(m.count for m in self.table_matches)


def group_tables_by_master_dataset(
    matches: List[_TableMatchResult],
) -> List[_DatasetMatch]:
    if matches == []:
        return []

    match_table_filter = reduce(
        operator.or_, (Q(schema=match.schema, table=match.table) for match in matches)
    )

    table_to_master_map = {}

    queryset = (
        SourceTable.objects.filter(match_table_filter)
        .values('schema', 'table')
        .annotate(
            master_id=F('dataset__id'),
            master_slug=F('dataset__slug'),
            master_name=F('dataset__name'),
        )
    )

    for row in queryset:
        table_to_master_map[(row["schema"], row["table"])] = {
            "id": row["master_id"],
            "slug": row["master_slug"],
            "name": row["master_name"],
        }

    masters = {}
    for match in matches:
        if (match.schema, match.table) not in table_to_master_map:
            continue

        master_blob = table_to_master_map[(match.schema, match.table)]

        if master_blob["id"] not in masters:
            masters[master_blob["id"]] = _DatasetMatch(
                id=master_blob["id"],
                slug=master_blob["slug"],
                name=master_blob["name"],
                table_matches=[],
            )

        masters[master_blob["id"]].table_matches.append(match)

    masters = list(masters.values())
    for master in masters:
        master.table_matches = sorted(master.table_matches, key=lambda t: -t.count)

    return sorted(masters, key=lambda r: -r.count)


def _enrich_and_suppress_matches(request, matches: Iterable[_TableMatchResult]):
    # Filter down to only tables that are in results from ES
    match_table_filter = reduce(
        operator.or_, (Q(schema=match.schema, table=match.table) for match in matches)
    )

    queryset = SourceTable.objects.filter(match_table_filter)

    no_access_filter = Q(dataset__user_access_type='REQUIRES_AUTHORIZATION') & ~Q(
        dataset__datasetuserpermission__user=request.user
    )

    # Pull out just the information we need
    tables_with_access_info = queryset.values(
        'schema', 'table', 'dataset_finder_opted_in', 'name'
    ).annotate(
        has_access=Case(
            When(no_access_filter, then=False),
            default=True,
            output_field=BooleanField(),
        )
    )

    mapped_tables = {(t['schema'], t['table']): t for t in tables_with_access_info}

    visible_matches = []
    has_suppressed_results = False
    for match in matches:
        key = (match.schema, match.table)

        if key not in mapped_tables:
            continue

        if (
            not mapped_tables[key]['dataset_finder_opted_in']
            and not mapped_tables[key]['has_access']
        ):
            has_suppressed_results = True
            continue

        match.name = mapped_tables[key]['name']
        match.has_access = mapped_tables[key]['has_access']
        visible_matches.append(match)

    return visible_matches, has_suppressed_results


def get_index_aliases_for_all_published_source_tables():
    return list(
        o['index_alias']
        for o in SourceTable.objects.filter(
            dataset__published=True, dataset__deleted=False
        ).values(index_alias=Concat('schema', Value('--'), 'table'))
    )


def log_query(user, query):
    return DatasetFinderQueryLog.objects.create(user=user, query=query)
