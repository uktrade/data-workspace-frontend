import json

import requests
from mohawk import Sender

from django.conf import settings


API_URL = f"{settings.DATAFLOW_API_CONFIG['DATAFLOW_BASE_URL']}/api/derived-dags/dag"
HAWK_CREDS = {
    "id": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_ID"],
    "key": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_KEY"],
    "algorithm": "sha256",
}


def save_pipeline_to_dataflow(pipeline):
    url = f"{API_URL}/{pipeline.dag_id}"
    method = "POST"
    content_type = "application/json"
    table_name, schema_name = pipeline.table_name.split(".")
    body = json.dumps(
        {
            "schema_name": schema_name,
            "table_name": table_name,
            "type": "sql",
            "config": {
                "sql": pipeline.sql_query,
            },
        }
    )
    header = Sender(
        HAWK_CREDS,
        url,
        method.lower(),
        content=body,
        content_type=content_type,
    ).request_header
    response = requests.request(
        method,
        url,
        data=body,
        headers={"Authorization": header, "Content-Type": content_type},
    )
    response.raise_for_status()
    return response.json()


def delete_pipeline_from_dataflow(pipeline):
    url = f"{API_URL}/{pipeline.dag_id}"
    method = "DELETE"
    content_type = ""
    header = Sender(
        HAWK_CREDS,
        url,
        method.lower(),
        content="",
        content_type=content_type,
    ).request_header
    response = requests.request(
        method,
        url,
        headers={"Authorization": header, "Content-Type": ""},
    )
    response.raise_for_status()
    return response.json()
