import logging

import boto3
import botocore
from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import (
    DataSet,
    VisualisationCatalogueItem,
    VisualisationLink,
)
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.cel import celery_app
from dataworkspace.datasets_db import (
    extract_queried_tables_from_sql_query,
    get_tables_last_updated_date,
)


logger = logging.getLogger('app')


def find_dataset(dataset_uuid, user):
    dataset = get_object_or_404(DataSet.objects.live(), id=dataset_uuid)

    if user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(dataset.type)
    ):
        return dataset

    if not dataset.published:
        raise Http404('No dataset matches the given query.')

    return dataset


def find_visualisation(visualisation_uuid, user):
    visualisation = get_object_or_404(
        VisualisationCatalogueItem.objects.live(), id=visualisation_uuid
    )

    if user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(
            DataSetType.VISUALISATION.value
        )
    ):
        return visualisation

    if not visualisation.published:
        raise Http404('No visualisation matches the given query.')

    return visualisation


def find_dataset_or_visualisation(model_id, user):
    if DataSet.objects.filter(pk=model_id):
        return find_dataset(model_id, user)

    return find_visualisation(model_id, user)


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    return {
        DataSetType.REFERENCE.value: 'datasets.manage_unpublished_reference_datasets',
        DataSetType.MASTER.value: 'datasets.manage_unpublished_master_datasets',
        DataSetType.DATACUT.value: 'datasets.manage_unpublished_datacut_datasets',
        DataSetType.VISUALISATION.value: 'datasets.manage_unpublished_visualisations',
    }[dataset_type]


def get_sql_snippet(schema, table_name, limit=50):
    return f"""SELECT * FROM "{schema}"."{table_name}" LIMIT {limit}"""


def get_code_snippets(source_table):
    if not hasattr(source_table, 'schema') or not hasattr(source_table, 'table'):
        return {}

    schema, table_name = source_table.schema, source_table.table
    python_snippet = f"""import os
import pandas
import psycopg2
import sqlalchemy

conn = psycopg2.connect(os.environ['DATABASE_DSN__datasets_1'])
engine = sqlalchemy.create_engine('postgresql://', creator=lambda: conn, execution_options={{"stream_results": True}})
chunks = pandas.read_sql('SELECT * FROM "{schema}"."{table_name}" LIMIT 50', engine, chunksize=10000)
for chunk in chunks:
    display(chunk)"""

    r_snippet = f"""library(stringr)
library(DBI)
getConn <- function(dsn) {{
    user <- str_match(dsn, "user=([a-z0-9_]+)")[2]
    password <- str_match(dsn, "password=([a-zA-Z0-9_]+)")[2]
    port <- str_match(dsn, "port=(\\\\d+)")[2]
    dbname <- str_match(dsn, "dbname=([a-z0-9_\\\\-]+)")[2]
    host <- str_match(dsn, "host=([a-z0-9_\\\\-\\\\.]+)")[2]
    con <- dbConnect(RPostgres::Postgres(), user = user, password = password, host = host, port = port, dbname = dbname)
    return(con)
}}
conn <- getConn(Sys.getenv('DATABASE_DSN__datasets_1'))

res <- dbSendQuery(conn, 'SELECT * FROM "{schema}"."{table_name}" LIMIT 50')
while (!dbHasCompleted(res)) {{
    chunk <- dbFetch(res, n = 50)
    print(chunk)
}}"""

    return {
        "python": python_snippet,
        "r": r_snippet,
        "sql": get_sql_snippet(schema, table_name),
    }


@celery_app.task()
def update_quicksight_visualisations_last_updated_date():
    """
    When setting the QuickSight VisualisationLink's modified_date, the following rules are applied:

    - Is it a SPICE visualisation?
        = Yes
          Use the DataSet's LastUpdatedTime
        = No
          - Is it a RelationalTable dataset?
              = Yes
                Use the table's last updated date
              = No
                - Is it a CustomSql dataset?
                    = Yes
                      Extract the tables from the query and use the most recent last updated date
                    = No
                      - Is it an S3Source dataset?
                        = Yes
                          Use the DataSet's LastUpdatedTime

    Each dashboard can have multiple DataSets and each DataSet can have multiple mappings, i.e it can have
    both RelationalTable and CustomSql mappings. Therefore a list of potential last updated dates is made and
    the most recent date from this list is chosen for the VisualisationLink's modified_date.
    """

    def get_last_updated_date_by_sql_query(query):
        for _, database_data in settings.DATABASES_DATA.items():
            tables = extract_queried_tables_from_sql_query(database_data['NAME'], query)
            if tables:
                date = get_tables_last_updated_date(
                    database_data['NAME'], tuple(tables)
                )
                if date:
                    return date
        return None

    def get_last_updated_date_by_table_name(schema, table):
        for _, database_data in settings.DATABASES_DATA.items():
            date = get_tables_last_updated_date(
                database_data['NAME'], ((schema, table),)
            )
            if date:
                return date
        return None

    account_id = boto3.client('sts').get_caller_identity().get('Account')
    quicksight_client = boto3.client('quicksight')
    logger.info('Fetching last updated dates for QuickSight visualisation links')

    for visualisation_link in VisualisationLink.objects.filter(
        visualisation_type='QUICKSIGHT'
    ):
        dashboard_id = visualisation_link.identifier
        logger.info('Fetching last updated date for DashboardId %s', dashboard_id)
        try:
            dashboard = quicksight_client.describe_dashboard(
                AwsAccountId=account_id, DashboardId=dashboard_id
            )['Dashboard']
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.error('DashboardId %s not found', dashboard_id)
                continue
            else:
                raise e
        else:
            data_set_arns = dashboard['Version']['DataSetArns']
            logger.info(
                'Found %d DataSets for DashboardId %s',
                len(data_set_arns),
                dashboard_id,
            )
            last_updated_dates = []

            for data_set_arn in data_set_arns:
                try:
                    data_set = quicksight_client.describe_data_set(
                        AwsAccountId=account_id, DataSetId=data_set_arn[50:]
                    )['DataSet']
                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        logger.error('DataSetId %s not found', data_set_arn[50:])
                        continue
                    else:
                        raise e
                else:
                    logger.info(
                        'Fetching last updated date for %s DataSet %s',
                        data_set['ImportMode'],
                        data_set['DataSetId'],
                    )
                    data_set_last_updated_time = data_set['LastUpdatedTime']
                    if data_set['ImportMode'] == 'SPICE':
                        last_updated_dates.append(data_set_last_updated_time)
                    else:
                        for table_map in data_set['PhysicalTableMap'].values():
                            data_set_type = list(table_map)[0]
                            if data_set_type == 'RelationalTable':
                                last_updated_date_candidate = (
                                    get_last_updated_date_by_table_name(
                                        table_map['RelationalTable']['Schema'],
                                        table_map['RelationalTable']['Name'],
                                    )
                                    or data_set_last_updated_time
                                )
                            elif data_set_type == 'CustomSql':
                                last_updated_date_candidate = (
                                    get_last_updated_date_by_sql_query(
                                        table_map['CustomSql']['SqlQuery']
                                    )
                                    or data_set_last_updated_time
                                )
                            elif data_set_type == 'S3Source':
                                last_updated_date_candidate = data_set_last_updated_time

                            last_updated_dates.append(last_updated_date_candidate)

            logger.info(
                'Setting last updated date of %s for DashboardId %s',
                max(last_updated_dates).strftime('%d-%m-%Y %H:%M:%S'),
                dashboard_id,
            )
            VisualisationLink.objects.filter(pk=visualisation_link.pk).update(
                modified_date=max(last_updated_dates)
            )

    logger.info(
        'Finished fetching last updated dates for QuickSight visualisation links'
    )
