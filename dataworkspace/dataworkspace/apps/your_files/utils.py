import csv
import json
import logging
import os
import re
from io import StringIO

import requests
from django.conf import settings
from mohawk import Sender
from tableschema import Schema

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    db_role_schema_suffix_for_user,
)
from dataworkspace.apps.your_files.constants import PostgresDataTypes

logger = logging.getLogger("app")


SCHEMA_POSTGRES_DATA_TYPE_MAP = {
    "integer": PostgresDataTypes.INTEGER,
    "boolean": PostgresDataTypes.BOOLEAN,
    "date": PostgresDataTypes.DATE,
    "datetime": PostgresDataTypes.TIMESTAMP,
    "numeric": PostgresDataTypes.NUMERIC,
    "text": PostgresDataTypes.TEXT,
    "uuid": PostgresDataTypes.UUID,
}
TABLESCHEMA_FIELD_TYPE_MAP = {
    "number": "numeric",
}


def get_s3_csv_file_info(path):
    client = get_s3_client()

    logger.debug(path)

    file = client.get_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path, Range="bytes=0-102400")
    raw = file["Body"].read()

    encoding, decoded = _get_encoding_and_decoded_bytes(raw)

    fh = StringIO(decoded, newline="")
    rows = list(csv.reader(fh))

    return {"encoding": encoding, "column_definitions": _get_csv_column_types(rows)}


def _get_encoding_and_decoded_bytes(raw: bytes):
    encoding = "utf-8-sig"

    try:
        decoded = raw.decode(encoding)
        return encoding, decoded
    except UnicodeDecodeError:
        pass

    try:
        encoding = "cp1252"
        decoded = raw.decode(encoding)
        return encoding, decoded
    except UnicodeDecodeError:
        pass

    # fall back of last resort will decode most things
    # https://docs.python.org/3/library/codecs.html#error-handlers
    encoding = "latin1"
    decoded = raw.decode(encoding, errors="replace")

    return encoding, decoded


def _get_csv_column_types(rows):
    if len(rows) <= 2:
        raise ValueError("Unable to read enough lines of data from file")

    # Drop the last line, which might be incomplete
    del rows[-1]

    # Pare down to a max of 10 lines so that inferring datatypes is quicker
    del rows[10:]

    schema = Schema()
    schema.infer(rows, confidence=1, headers=1)

    fields = []
    for idx, field in enumerate(schema.descriptor["fields"]):
        fields.append(
            {
                "header_name": field["name"],
                "column_name": clean_db_identifier(field["name"]),
                "data_type": SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                    TABLESCHEMA_FIELD_TYPE_MAP.get(field["type"], field["type"]),
                    PostgresDataTypes.TEXT,
                ),
                "sample_data": [row[idx] for row in rows][:6],
            }
        )

    return fields


def trigger_dataflow_dag(conf, dag, dag_run_id):
    config = settings.DATAFLOW_API_CONFIG
    trigger_url = f'{config["DATAFLOW_BASE_URL"]}/api/experimental/' f"dags/{dag}/dag_runs"
    logger.debug("trigger_dataflow_dag %s", trigger_url)
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    logger.info(hawk_creds)
    method = "POST"
    content_type = "application/json"
    body = json.dumps(
        {
            "run_id": dag_run_id,
            "replace_microseconds": "false",
            "conf": conf,
        }
    )

    header = Sender(
        hawk_creds,
        trigger_url,
        method.lower(),
        content=body,
        content_type=content_type,
    ).request_header

    response = requests.request(
        method,
        trigger_url,
        data=body,
        headers={"Authorization": header, "Content-Type": content_type},
    )

    logger.debug(response.status_code)
    response.raise_for_status()
    return response.json()


def clean_db_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[-1])[0]
    identifier = re.sub(r"[^\w\s-]", "", identifier).strip().lower()
    return re.sub(r"[-\s]+", "_", identifier)


def copy_file_to_uploads_bucket(from_path, to_path):
    client = get_s3_client()

    try:
        client.copy_object(
            CopySource={"Bucket": settings.NOTEBOOKS_BUCKET, "Key": from_path},
            Bucket=settings.AWS_UPLOADS_BUCKET,
            Key=to_path,
        )
    except Exception:
        logger.error("failed to copy file to uploads bucket")
        raise


def get_dataflow_dag_status(dag, execution_date):
    config = settings.DATAFLOW_API_CONFIG
    url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/'
        f'dags/{dag}/dag_runs/{execution_date.split("+")[0]}'
    )
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    header = Sender(
        hawk_creds,
        url,
        "get",
        content="",
        content_type="",
    ).request_header
    response = requests.get(
        url,
        headers={"Authorization": header, "Content-Type": ""},
    )
    response.raise_for_status()
    return response.json()


def get_dataflow_task_status(dag, execution_date, task_id):
    config = settings.DATAFLOW_API_CONFIG
    url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/'
        f"dags/{dag}/dag_runs/"
        f'{execution_date.split("+")[0]}/tasks/{task_id}'
    )
    hawk_creds = {
        "id": config["DATAFLOW_HAWK_ID"],
        "key": config["DATAFLOW_HAWK_KEY"],
        "algorithm": "sha256",
    }
    header = Sender(hawk_creds, url, "get", content="", content_type="").request_header
    response = requests.get(url, headers={"Authorization": header, "Content-Type": ""})
    response.raise_for_status()
    return response.json().get("state")


def get_user_schema(request):
    return f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(request.user)}"


def get_schema_for_user(user):
    return f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(user)}"
