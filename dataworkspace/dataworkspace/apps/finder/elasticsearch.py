from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings

from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

import boto3


@dataclass
class _TableMatchResult:
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
                        'host': settings.DATASET_FINDER_ES_HOST,
                        'port': settings.DATASET_FINDER_ES_PORT,
                    },
                ],
                timeout=60,
                connection_class=RequestsHttpConnection,
            )
        else:
            region = settings.DATASET_FINDER_AWS_REGION

            credentials = boto3.Session().get_credentials()
            self._aws_auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                'es',
                session_token=credentials.token,
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

    def search_for_phrase(
        self, phrase: str, indexes: List[str]
    ) -> List[_TableMatchResult]:
        resp = self._client.search(
            body={
                "query": {"match_phrase": {"_all": phrase}},
                "aggs": {"indexes": {"terms": {"field": "_index"}}},
            },
            index=','.join(indexes),
            ignore_unavailable=True,
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
