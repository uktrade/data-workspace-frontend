from dataclasses import dataclass
from typing import List

from django.conf import settings

from django.db import connections

from dataworkspace.apps.finder.elasticsearch import _TableMatchResult


@dataclass
class _DatasetMatch:
    id: str
    slug: str
    name: str
    table_matches: List[_TableMatchResult]

    @property
    def count(self):
        return sum(m.count for m in self.table_matches)


def group_matches_by_master(matches: List[_TableMatchResult]) -> List[_DatasetMatch]:
    schemas_and_tables = list({(m.schema, m.table) for m in matches})

    table_to_master_map = {}
    with connections[settings.DATASET_FINDER_DB_NAME].cursor() as cursor:
        condition = " OR ".join(
            f"(s.schema = '{schema}' AND s.table = '{table}')"
            for schema, table in schemas_and_tables
        )
        cursor.execute(
            f"""
            SELECT s.schema, s.table, s.name, c.id AS master_id, c.slug AS master_slug, c.name AS master_name
            FROM dataworkspace__source_tables AS s
            INNER JOIN dataworkspace__catalogue_items AS c ON s.dataset_id = c.id
            WHERE {condition}
        """
        )

        def _dictfetchall(cursor):
            "Return all rows from a cursor as a dict"
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        for r in _dictfetchall(cursor):
            table_to_master_map[(r["schema"], r["table"])] = {
                "id": r["master_id"],
                "slug": r["master_slug"],
                "master": r["master_name"],
                "name": r["name"],
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
                name=master_blob["master"],
                table_matches=[],
            )

        match.name = master_blob["name"]

        masters[master_blob["id"]].table_matches.append(match)

    masters = list(masters.values())
    for master in masters:
        master.table_matches = sorted(master.table_matches, key=lambda t: -t.count)

    return sorted(masters, key=lambda r: -r.count)
