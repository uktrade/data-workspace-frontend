import csv
import json
import os
import re

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

    sample_csv_data = []
    for count, line in enumerate(file['Body'].iter_lines()):
        sample_csv_data.append(line.decode('utf-8'))
        if count > 9:
            break

    reader = csv.reader(sample_csv_data)
    schema = Schema()
    schema.infer(list(reader), confidence=1, headers=1)

    fields = []
    for field in schema.descriptor['fields']:
        fields.append(
            {
                'header_name': field['name'],
                'column_name': clean_db_identifier(field['name']),
                'data_type': SCHEMA_POSTGRES_DATA_TYPE_MAP.get(
                    field['type'], PostgresDataTypes.TEXT.value
                ),
            }
        )
    return fields


def trigger_dataflow_dag(path, schema, table, column_definitions, dag_run_id):
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
            'run_id': dag_run_id,
            'conf': {
                'db_role': schema,
                'file_path': path,
                'schema_name': schema,
                'table_name': table,
                'column_definitions': column_definitions,
            },
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


def clean_db_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[-1])[0]
    identifier = re.sub(r'[^\w\s-]', '', identifier).strip().lower()
    return re.sub(r'[-\s]+', '_', identifier)


def copy_file_to_uploads_bucket(from_path, to_path):
    client = boto3.client('s3')
    client.copy_object(
        CopySource={'Bucket': settings.NOTEBOOKS_BUCKET, 'Key': from_path},
        Bucket=settings.AWS_UPLOADS_BUCKET,
        Key=to_path,
    )
