import json
import re

import requests
from mohawk import Sender

from django.conf import settings


API_URL = f"{settings.DATAFLOW_API_CONFIG['DATAFLOW_BASE_URL']}/api/experimental/derived-dags"
HAWK_CREDS = {
    "id": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_ID"],
    "key": settings.DATAFLOW_API_CONFIG["DATAFLOW_HAWK_KEY"],
    "algorithm": "sha256",
}


def split_schema_table(schema_table):
    regex = r"^\"?([a-zA-Z_-][a-zA-Z0-9_-]+)\"?\.\"?([a-zA-Z_-][a-zA-Z0-9_-]+)\"?$"
    try:
        return re.match(regex, schema_table).groups()
    except AttributeError as ex:
        raise ValueError("Invalid schema table name") from ex


def save_pipeline_to_dataflow(pipeline, method):
    url = f"{API_URL}/dag/{pipeline.dag_id}"
    content_type = "application/json"
    schema_name, table_name = split_schema_table(pipeline.table_name)
    body = json.dumps(
        {
            "schedule": pipeline.schedule,
            "schema_name": schema_name,
            "table_name": table_name,
            "type": pipeline.type,
            "enabled": True,
            "config": pipeline.config,
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


def run_pipeline(pipeline):
    url = f"{API_URL}/dag/{pipeline.dag_id}/run"
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
