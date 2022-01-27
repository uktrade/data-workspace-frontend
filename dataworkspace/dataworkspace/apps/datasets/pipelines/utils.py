import json

import requests
from mohawk import Sender

from django.conf import settings


API_URL = f"{settings.DATAFLOW_API_CONFIG['DATAFLOW_BASE_URL']}/api/experimental/derived-dags"
HAWK_CREDS = {
    "id": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_ID"],
    "key": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_KEY"],
    "algorithm": "sha256",
}


def save_pipeline_to_dataflow(pipeline, method):
    url = f"{API_URL}/dag/{pipeline.dag_id}"
    content_type = "application/json"
    schema_name, table_name = pipeline.table_name.split(".")
    body = json.dumps(
        {
            "schedule": "@daily",
            "schema_name": schema_name,
            "table_name": table_name,
            "type": "sql",
            "enabled": True,
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
    url = f"{API_URL}/dag/{pipeline.dag_id}"
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


def run_pipeline(pipeline, run_by_user):
    url = (
        f"{settings.DATAFLOW_API_CONFIG['DATAFLOW_BASE_URL']}/api/experimental/"
        f"dags/{pipeline.dag_id}/dag_runs"
    )
    method = "POST"
    content_type = "application/json"
    body = json.dumps(
        {"replace_microseconds": "false", "conf": {"run_by_user": run_by_user.get_full_name()}}
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


def stop_pipeline(pipeline, run_by_user):
    url = f"{API_URL}/dag/{pipeline.dag_id}/stop"
    method = "POST"
    content_type = "application/json"
    body = ""
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


def list_pipelines():
    url = f"{API_URL}/dags"
    method = "GET"
    content_type = "application/json"
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
        headers={"Authorization": header, "Content-Type": content_type},
    )
    response.raise_for_status()
    return response.json()


def get_pipeline_logs(pipeline):
    url = f"{API_URL}/dag/{pipeline.dag_id}/logs"

    method = "GET"
    content_type = "application/json"
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
        headers={"Authorization": header, "Content-Type": content_type},
    )
    response.raise_for_status()
    return response.json()
