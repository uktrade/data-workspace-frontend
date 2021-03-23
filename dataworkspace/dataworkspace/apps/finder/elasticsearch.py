from dataclasses import dataclass
from typing import List, Optional
from django.conf import settings

from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection


@dataclass
class _TableMatchResult:
    schema: str
    table: str
    count: int
    name: Optional[str] = None


class ElasticsearchClient:
    def __init__(self, *args, **kwargs):
        if settings.DATASET_FINDER_ES_INSECURE:
            self._client = Elasticsearch(
                hosts=[
                    {
                        'host': settings.DATASET_FINDER_ES_HOST,
                        'port': settings.DATASET_FINDER_ES_PORT,
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
                aws_service='es',
            )
            self._client = Elasticsearch(
                hosts=[
                    {
                        'host': settings.DATASET_FINDER_ES_HOST,
                        'port': settings.DATASET_FINDER_ES_PORT,
                    },
                ],
                http_auth=self._aws_auth,
                use_ssl=True,
                verify_certs=True,
                timeout=60,
                connection_class=RequestsHttpConnection,
            )

    def find_tables_containing_term(self, term: str) -> List[_TableMatchResult]:
        resp = self._client.search(
            body={
                "query": {"match_phrase": {"_all": term}},
                "aggs": {"indexes": {"terms": {"field": "_index"}}},
            },
            size=0,
        )

        results = []

        if resp['hits']['total']['value'] > 0:
            for r in resp["aggregations"]["indexes"]["buckets"]:
                # The Elasticsearch index names have a structured format:
                # {timestamp}--{schema}--{table}--{arbitrary_number}
                _, schema, table, _ = r['key'].split('--')
                results.append(
                    _TableMatchResult(schema=schema, table=table, count=r["doc_count"])
                )

        return sorted(results, key=lambda x: -x.count)


es_client = ElasticsearchClient()
