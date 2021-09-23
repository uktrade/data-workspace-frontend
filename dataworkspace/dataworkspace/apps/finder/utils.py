import operator
from dataclasses import dataclass
from functools import reduce
from typing import List, Iterable

from django.db.models import Q, Case, When, BooleanField, Value
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
    has_access: bool

    @property
    def count(self):
        return sum(m.count for m in self.table_matches)


def group_tables_by_master_dataset(
    matches: List[_TableMatchResult], user
) -> List[_DatasetMatch]:
    if matches == []:
        return []

    match_table_filter = reduce(
        operator.or_, (Q(schema=match.schema, table=match.table) for match in matches)
    )

    table_to_master_map = {}
    for source_table in SourceTable.objects.filter(match_table_filter):
        table_to_master_map[(source_table.schema, source_table.table)] = {
            "id": source_table.dataset.id,
            "slug": source_table.dataset.slug,
            "name": source_table.dataset.name,
            "has_access": source_table.dataset.user_has_access(user),
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
                has_access=master_blob["has_access"],
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


class ResultsProxy:
    """
    A proxy object for returning Elasticsearch results that is able to be
    passed to a Paginator.
    """

    def __init__(self, es_client, index_alias, phrase, count):
        super(ResultsProxy, self).__init__()
        self._client = es_client
        self.index_alias = index_alias
        self.phrase = phrase
        self.count = count

    def __len__(self):
        return self.count

    def __getitem__(self, item):
        assert isinstance(item, slice)

        resp = self._client.search(
            phrase=self.phrase,
            index_aliases=[self.index_alias],
            from_=item.start,
            size=item.stop - item.start,
        )

        return resp['hits']['hits']
