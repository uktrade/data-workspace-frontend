from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from django.conf import settings

from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection


@dataclass
class _TableMatchResult:
    index: str
    schema: str
    table: str
    count: int
    has_access: bool = False
    name: Optional[str] = None


class ElasticsearchClient:
    def __init__(self, *args, **kwargs):
        if settings.DATASET_FINDER_ES_INSECURE:
            self._client = Elasticsearch(
                hosts=[
                    {
                        "host": settings.DATASET_FINDER_ES_HOST,
                        "port": settings.DATASET_FINDER_ES_PORT,
                    },
                ],
                timeout=60,
                connection_class=RequestsHttpConnection,
            )
        else:
            region = settings.DATASET_FINDER_AWS_REGION

            self._aws_auth = BotoAWSRequestsAuth(
                aws_host=settings.DATASET_FINDER_ES_HOST,
                aws_region=region,
                aws_service="es",
            )
            self._client = Elasticsearch(
                hosts=[
                    {
                        "host": settings.DATASET_FINDER_ES_HOST,
                        "port": settings.DATASET_FINDER_ES_PORT,
                    },
                ],
                http_auth=self._aws_auth,
                use_ssl=True,
                verify_certs=True,
                timeout=60,
                connection_class=RequestsHttpConnection,
            )

    @property
    def client(self):
        return self._client

    def _batch_indexes(self, index_aliases, batch_size=100):
        lists_of_indexes = []
        for i, alias in enumerate(index_aliases, start=0):
            if i % batch_size == 0:
                lists_of_indexes.append([])
                i += 1

            lists_of_indexes[-1].append(alias)

        return lists_of_indexes

    def search(
        self,
        phrase: str,
        index_aliases: List[str],
        from_: int,
        size: int,
        filters: List[dict] = None,
    ):
        queries = [
            {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": phrase,
                            "type": "phrase",
                            "fields": ["_all"],
                        }
                    }
                }
            }
        ] + (filters if filters else [])

        # pylint: disable=unexpected-keyword-arg
        return self._client.search(
            body={
                "sort": [{"_id": {"order": "asc"}}],
                "query": {"bool": {"must": queries}},
                "aggs": {"indexes": {"terms": {"field": "_index"}}},
            },
            index=",".join(index_aliases),
            ignore_unavailable=True,
            from_=from_,
            size=size,
        )

    def search_for_phrase(
        self,
        phrase: str,
        index_aliases: List[str],
        filters: Tuple[Tuple[str, Any]] = None,
    ) -> List[_TableMatchResult]:
        results = []

        for batch in self._batch_indexes(index_aliases):
            resp = self.search(phrase, batch, 0, 0, filters=filters)

            if resp["hits"]["total"]["value"] > 0:
                for r in resp["aggregations"]["indexes"]["buckets"]:
                    # The Elasticsearch index names have a structured format:
                    # {timestamp}--{schema}--{table}--{arbitrary_number}
                    _, schema, table, _ = r["key"].split("--")
                    results.append(
                        _TableMatchResult(
                            index=r["key"],
                            schema=schema,
                            table=table,
                            count=r["doc_count"],
                        )
                    )

        return sorted(results, key=lambda x: -x.count)

    def get_count(self, phrase, index_alias, filters: Tuple[Tuple[str, Any]] = None):
        matches = self.search_for_phrase(phrase, [index_alias], filters=filters)
        if matches:
            return matches[0].count
        return 0

    def get_fields(self, index_alias):
        """
        Return a list of the fields stored in an elasticsearch index
        """
        mapping = self.client.indices.get_mapping(index_alias)
        return list(list(mapping.values())[0]["mappings"]["properties"].keys())


es_client = ElasticsearchClient()
