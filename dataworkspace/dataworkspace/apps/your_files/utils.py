import csv
import json
import os
import re
from io import StringIO

import boto3
import requests

from django.conf import settings
from mohawk import Sender
from tableschema import Schema

from dataworkspace.apps.your_files.constants import PostgresDataTypes

SCHEMA_POSTGRES_DATA_TYPE_MAP = {
    'integer': PostgresDataTypes.INTEGER.value,
    'boolean': PostgresDataTypes.BOOLEAN.value,
    'date': PostgresDataTypes.DATE.value,
    'datetime': PostgresDataTypes.TIMESTAMP.value,
    'number': PostgresDataTypes.NUMERIC.value,
    'text': PostgresDataTypes.TEXT.value,
}


def get_s3_csv_column_types(path):
    client = boto3.client('s3')
    file = client.get_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path)

    csv_data = ''
    for count, line in enumerate(file['Body'].iter_lines()):
        csv_data += str(line) + '\n'
        if count > 9:
            break

    reader = csv.reader(StringIO(csv_data))
    schema = Schema()
    schema.infer(list(reader), confidence=1, headers=1)

    field_map = {}
    for field in schema.descriptor['fields']:
        field_map[field['name']] = SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
            field['type'], PostgresDataTypes.TEXT.value
        )
    return field_map


def trigger_dataflow_dag(path, schema, table, column_definitions):
    config = settings.DATAFLOW_API_CONFIG
    trigger_url = (
        f'{config["DATAFLOW_BASE_URL"]}/api/experimental/'
        f'dags/{config["DATAFLOW_S3_IMPORT_DAG"]}/dag_runs'
    )
    hawk_creds = {
        'id': config['DATAFLOW_HAWK_ID'],
        'key': config['DATAFLOW_HAWK_KEY'],
        'algorithm': 'sha256',
    }
    method = 'POST'
    content_type = 'application/json'
    body = json.dumps(
        {
            'conf': {
                'file_path': path,
                'data_uploader_schema_name': schema,
                'data_uploader_table_name': table,
                'column_definitions': column_definitions,
            }
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
        headers={'Authorization': header, 'Content-Type': content_type},
    )
    response.raise_for_status()


def s3_path_to_table_name(path):
    file_name = os.path.splitext(os.path.split(path)[-1])[0]
    file_name = re.sub(r'[^\w\s-]', '', file_name).strip().lower()
    return re.sub(r'[-\s]+', '_', file_name)


def copy_file_to_uploads_bucket(from_path, to_path):
    client = boto3.client('s3')
    client.copy(
        {'Bucket': settings.NOTEBOOKS_BUCKET, 'Key': from_path},
        settings.AWS_UPLOADS_BUCKET,
        to_path,
    )
