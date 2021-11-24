import json
import logging
import operator
import os
from functools import reduce
from uuid import UUID

import boto3
import botocore
from django.conf import settings
from django.http import Http404
from django.db import connections
from django.db.models import Q
from django.shortcuts import get_object_or_404
from psycopg2.sql import Identifier, Literal, SQL
import requests

from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    CustomDatasetQueryTable,
    DataSet,
    DataSetType,
    ReferenceDataset,
    VisualisationCatalogueItem,
    VisualisationLink,
    VisualisationLinkSqlQuery,
)
from dataworkspace.cel import celery_app
from dataworkspace.datasets_db import (
    extract_queried_tables_from_sql_query,
    get_tables_last_updated_date,
)
from dataworkspace.apps.core.utils import close_all_connections_if_not_in_atomic_block
from dataworkspace.utils import TYPE_CODES_REVERSED

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
            DataSetType.VISUALISATION
        )
    ):
        return visualisation

    if not visualisation.published:
        raise Http404('No visualisation matches the given query.')

    return visualisation


def find_dataset_or_visualisation(model_id, user):
    if DataSet.objects.filter(pk=model_id).exists():
        return find_dataset(model_id, user)

    return find_visualisation(model_id, user)


def find_dataset_or_visualisation_for_bookmark(model_id):
    if DataSet.objects.filter(pk=model_id).exists():
        return get_object_or_404(DataSet.objects.live(), id=model_id)

    if ReferenceDataset.objects.filter(uuid=model_id).exists():
        return get_object_or_404(ReferenceDataset.objects.live(), uuid=model_id)

    return get_object_or_404(VisualisationCatalogueItem.objects.live(), id=model_id)


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    return {
        DataSetType.REFERENCE: 'datasets.manage_unpublished_reference_datasets',
        DataSetType.MASTER: 'datasets.manage_unpublished_master_datasets',
        DataSetType.DATACUT: 'datasets.manage_unpublished_datacut_datasets',
        DataSetType.VISUALISATION: 'datasets.manage_unpublished_visualisations',
    }[dataset_type]


def get_code_snippets_for_table(source_table):
    if not hasattr(source_table, 'schema') or not hasattr(source_table, 'table'):
        return {'python': '', 'r': '', 'sql': ''}
    query = get_sql_snippet(source_table.schema, source_table.table, 50)
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
    }


def get_code_snippets_for_reference_table(table):
    query = get_sql_snippet('public', table, 50)
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
    }


def get_code_snippets_for_query(query):
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
    }


def get_sql_snippet(schema, table_name, limit=50):
    return f'SELECT * FROM "{schema}"."{table_name}" LIMIT {limit}'


def get_python_snippet(query):
    """
    sqlalchemy.text() is used to make sure the sql string is in a form that sqlalchemy expects.
    `backslash`, `"` and `'''` are also escaped
    """
    query = query.replace('\\', '\\\\').replace('"', '\\"')
    return f"""import os
import pandas
import psycopg2
import sqlalchemy

conn = psycopg2.connect(os.environ['DATABASE_DSN__datasets_1'])
engine = sqlalchemy.create_engine('postgresql://', creator=lambda: conn, execution_options={{"stream_results": True}})
chunks = pandas.read_sql(sqlalchemy.text(\"""{query}\"""), engine, chunksize=10000)
for chunk in chunks:
    display(chunk)"""


def get_r_snippet(query):
    query = query.replace('\\', '\\\\').replace('"', '\\"')
    return f"""library(stringr)
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

res <- dbSendQuery(conn, \"{query}\")
while (!dbHasCompleted(res)) {{
    chunk <- dbFetch(res, n = 50)
    print(chunk)
}}"""


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def process_quicksight_dashboard_visualisations():
    """
    Loop over all VisualisationLink objects and do the following:

    1) Save each data set's CustomSql query in the VisalisationLink's sql_queries field
    2) Extract the tables from each data set's CustomSql query and save them in the
       VisualisationCatalogueItem's datasets field
    3) Set the VisualisationLink's data_source_last_updated using the following rules:
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
                        Use the max of Dashboard.LastPublishedTime, Dashboard.LastUpdatedTime,
                        DataSet.LastUpdatedTime
                        = No
                        - Is it an S3Source dataset?
                            = Yes
                            Use the DataSet's LastUpdatedTime

        Each dashboard can have multiple DataSets and each DataSet can have multiple mappings, i.e it can have
        both RelationalTable and CustomSql mappings. Therefore a list of potential last updated dates is made and
        the most recent date from this list is chosen for the VisualisationLink's data_source_last_updated.
    """

    def get_last_updated_date_by_table_name(schema, table):
        for connection_alias, _ in settings.DATABASES_DATA.items():
            date = get_tables_last_updated_date(connection_alias, ((schema, table),))
            if date:
                return date
        return None

    account_id = boto3.client('sts').get_caller_identity().get('Account')
    quicksight_client = boto3.client('quicksight')

    logger.info('Fetching last updated dates for QuickSight visualisation links')

    for visualisation_link in VisualisationLink.objects.filter(
        visualisation_type='QUICKSIGHT', visualisation_catalogue_item__deleted=False
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
            raise e
        else:
            data_set_arns = dashboard['Version']['DataSetArns']
            logger.info(
                'Found %d DataSets for DashboardId %s',
                len(data_set_arns),
                dashboard_id,
            )
            last_updated_dates = []
            tables = []
            database_name, _ = list(settings.DATABASES_DATA.items())[0]

            for data_set_arn in data_set_arns:
                try:
                    data_set = quicksight_client.describe_data_set(
                        AwsAccountId=account_id, DataSetId=data_set_arn[50:]
                    )['DataSet']
                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        logger.error('DataSetId %s not found', data_set_arn[50:])
                        continue
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

                        for table_id, table_map in data_set['PhysicalTableMap'].items():
                            data_set_type = list(table_map)[0]
                            if data_set_type == 'CustomSql':
                                store_sql_query(
                                    visualisation_link,
                                    data_set['DataSetId'],
                                    table_id,
                                    table_map['CustomSql']['SqlQuery'],
                                )
                                tables.extend(
                                    extract_queried_tables_from_sql_query(
                                        database_name,
                                        table_map['CustomSql']['SqlQuery'],
                                    )
                                )
                    else:
                        for table_id, table_map in data_set['PhysicalTableMap'].items():
                            data_set_type = list(table_map)[0]
                            if data_set_type == 'RelationalTable':
                                last_updated_date_candidate = (
                                    get_last_updated_date_by_table_name(
                                        table_map['RelationalTable']['Schema'],
                                        table_map['RelationalTable']['Name'],
                                    )
                                    or data_set_last_updated_time
                                )
                                tables.append(
                                    (
                                        table_map['RelationalTable']['Schema'],
                                        table_map['RelationalTable']['Name'],
                                    )
                                )
                            elif data_set_type == 'CustomSql':
                                store_sql_query(
                                    visualisation_link,
                                    data_set['DataSetId'],
                                    table_id,
                                    table_map['CustomSql']['SqlQuery'],
                                )
                                last_updated_date_candidate = max(
                                    dashboard['LastPublishedTime'],
                                    dashboard['LastUpdatedTime'],
                                    data_set['LastUpdatedTime'],
                                )
                                tables.extend(
                                    extract_queried_tables_from_sql_query(
                                        database_name,
                                        table_map['CustomSql']['SqlQuery'],
                                    )
                                )
                            elif data_set_type == 'S3Source':
                                last_updated_date_candidate = data_set_last_updated_time

                            last_updated_dates.append(last_updated_date_candidate)

            if last_updated_dates:
                logger.info(
                    'Setting last updated date of %s for DashboardId %s',
                    max(last_updated_dates).strftime('%d-%m-%Y %H:%M:%S'),
                    dashboard_id,
                )
                visualisation_link.data_source_last_updated = max(last_updated_dates)
                visualisation_link.save()

            if tables:
                set_dataset_related_visualisation_catalogue_items(
                    visualisation_link, tables
                )

    logger.info(
        'Finished fetching last updated dates for QuickSight visualisation links'
    )


def store_sql_query(visualisation_link, data_set_id, table_id, sql_query):
    try:
        visualisation_link.sql_queries.get(
            is_latest=True,
            data_set_id=data_set_id,
            table_id=table_id,
            sql_query=sql_query,
        )
    except VisualisationLinkSqlQuery.DoesNotExist:
        visualisation_link.sql_queries.filter(
            is_latest=True, data_set_id=data_set_id, table_id=table_id
        ).update(is_latest=False)
        VisualisationLinkSqlQuery.objects.create(
            data_set_id=data_set_id,
            table_id=table_id,
            sql_query=sql_query,
            is_latest=True,
            visualisation_link=visualisation_link,
        )


@celery_app.task()
def link_superset_visualisations_to_related_datasets():
    api_url = os.environ['SUPERSET_ROOT'] + '/api/v1/%s'

    login_response = requests.post(
        api_url % 'security/login',
        json={
            'username': os.environ['SUPERSET_DW_USER_USERNAME'],
            'password': os.environ['SUPERSET_DW_USER_PASSWORD'],
            'provider': 'db',
        },
    )
    if login_response.status_code != 200:
        logger.error(
            "Unable to authenticate with Superset API with error %s",
            login_response.content,
        )
        return

    jwt_access_token = login_response.json()['access_token']

    database_name, _ = list(settings.DATABASES_DATA.items())[0]

    for visualisation_link in VisualisationLink.objects.filter(
        visualisation_type='SUPERSET', visualisation_catalogue_item__deleted=False
    ):
        dashboard_id = int(visualisation_link.identifier)
        logger.info(
            "Setting related visualisations for Superset dashboard id %d", dashboard_id
        )

        tables = []
        datasets_response = requests.get(
            api_url % f'dashboard/{dashboard_id}/datasets',
            headers={'Authorization': f'Bearer {jwt_access_token}'},
        )
        if datasets_response.status_code != 200:
            logger.error(
                "Unable to get datasets for Superset dashboard id %d with error %s",
                dashboard_id,
                datasets_response.content,
            )
            continue

        datasets = datasets_response.json()['result']
        logger.info(
            'Found %d datasets for Superset dashboard id %d',
            len(datasets),
            dashboard_id,
        )

        for dataset in datasets:
            logger.info(
                'Extracting tables from dashboard id %d and dataset if %d',
                dashboard_id,
                dataset['id'],
            )

            tables.extend(
                extract_queried_tables_from_sql_query(database_name, dataset['sql'])
            )

        if tables:
            set_dataset_related_visualisation_catalogue_items(
                visualisation_link, tables
            )


def set_dataset_related_visualisation_catalogue_items(visualisation_link, tables):
    datasets = list(
        DataSet.objects.filter(
            reduce(
                operator.or_,
                (
                    [
                        Q(sourcetable__schema=t[0], sourcetable__table=t[1])
                        for t in tables
                    ]
                ),
            )
        )
        .distinct()
        .values_list('id', flat=True)
    )

    datacuts = list(
        CustomDatasetQueryTable.objects.filter(
            reduce(operator.or_, ([Q(schema=t[0], table=t[1]) for t in tables]),)
        )
        .distinct()
        .values_list('query__dataset__id', flat=True)
    )

    for object_id in datasets + datacuts:
        visualisation_link.visualisation_catalogue_item.datasets.add(object_id)


def build_filtered_dataset_query(inner_query, column_config, params):
    column_map = {x['field']: x for x in column_config}
    query_params = {
        'offset': int(params.get('start', 0)),
        'limit': params.get('limit'),
    }
    sort_dir = 'DESC' if params.get('sortDir', '').lower() == 'desc' else 'ASC'
    sort_fields = [column_config[0]['field']]
    if params.get('sortField') and params.get('sortField') in column_map:
        sort_fields = [params.get('sortField')]

    where_clause = []
    for field, filter_data in params.get('filters', {}).items():
        terms = [filter_data.get('filter'), filter_data.get('filterTo')]
        if filter_data['filterType'] == 'date':
            terms = [filter_data['dateFrom'], filter_data['dateTo']]

        if field in column_map:
            data_type = column_map[field].get('dataType', filter_data['filterType'])

            # Searching on invalid uuids will raise an exception.
            # To get around that, if the uuid is invalid we
            # force the query to return no results (`where 1 = 2`)
            if data_type == 'uuid':
                try:
                    UUID(terms[0], version=4)
                except ValueError:
                    where_clause.append(SQL('1 = 2'))
                    break

            # Booleans are passed as integers
            if data_type == 'boolean':
                terms[0] = bool(int(terms[0]))

            if data_type == 'text' and filter_data['type'] == 'contains':
                query_params[field] = f'%{terms[0]}%'
                where_clause.append(
                    SQL(f'lower({{}}) LIKE lower(%({field})s)').format(
                        Identifier(field)
                    )
                )
            elif data_type == 'text' and filter_data['type'] == 'notContains':
                query_params[field] = f'%{terms[0]}%'
                where_clause.append(
                    SQL(f'lower({{}}) NOT LIKE lower(%({field})s)').format(
                        Identifier(field)
                    )
                )
            elif filter_data['type'] == 'equals':
                query_params[field] = terms[0]
                if data_type == 'text':
                    where_clause.append(
                        SQL(f'lower({{}}) = lower(%({field})s)').format(
                            Identifier(field)
                        )
                    )
                else:
                    where_clause.append(
                        SQL(f'{{}} = %({field})s').format(Identifier(field))
                    )

            elif filter_data['type'] == 'notEqual':
                query_params[field] = terms[0]
                if data_type == 'text':
                    where_clause.append(
                        SQL(f'lower({{}}) != lower(%({field})s)').format(
                            Identifier(field)
                        )
                    )
                else:
                    where_clause.append(
                        SQL(f'{{}} is distinct from %({field})s').format(
                            Identifier(field)
                        )
                    )
            elif filter_data['type'] in ['startsWith', 'endsWith']:
                query_params[field] = (
                    f'{terms[0]}%'
                    if filter_data['type'] == 'startsWith'
                    else f'%{terms[0]}'
                )
                where_clause.append(
                    SQL(f'lower({{}}) LIKE lower(%({field})s)').format(
                        Identifier(field)
                    )
                )
            elif filter_data['type'] == 'inRange':
                where_clause.append(
                    SQL(f'{{}} BETWEEN %({field}_from)s AND %({field}_to)s').format(
                        Identifier(field)
                    )
                )
                query_params[f'{field}_from'] = terms[0]
                query_params[f'{field}_to'] = terms[1]
            elif filter_data['type'] in ['greaterThan', 'greaterThanOrEqual']:
                operator = '>' if filter_data['type'] == 'greaterThan' else '>='
                where_clause.append(
                    SQL(f'{{}} {operator} %({field})s').format(Identifier(field))
                )
                query_params[field] = terms[0]
            elif filter_data['type'] in ['lessThan', 'lessThanOrEqual']:
                query_params[field] = terms[0]
                operator = '<' if filter_data['type'] == 'lessThan' else '<='
                where_clause.append(
                    SQL(f'{{}} {operator} %({field})s').format(Identifier(field))
                )

    if where_clause:
        where_clause = SQL('WHERE') + SQL(' AND ').join(where_clause)

    query = SQL(
        f'''
        SELECT {{}}
        FROM ({{}}) a
        {{}}
        ORDER BY {{}} {sort_dir}
        LIMIT %(limit)s
        OFFSET %(offset)s
        '''
    ).format(
        SQL(',').join(map(Identifier, column_map)),
        inner_query,
        SQL(' ').join(where_clause),
        SQL(',').join(map(Identifier, sort_fields)),
    )

    return query, query_params


@celery_app.task()
def store_custom_dataset_query_table_structures():
    for query in CustomDatasetQuery.objects.filter(dataset__published=True):
        sql = query.query.rstrip().rstrip(';')

        tables = extract_queried_tables_from_sql_query(
            query.database.memorable_name, sql
        )
        tables_last_updated_date = get_tables_last_updated_date(
            query.database.memorable_name, tuple(tables)
        )
        query_last_updated_date = query.modified_date

        last_updated_date = max(tables_last_updated_date, query_last_updated_date)
        with connections[query.database.memorable_name].cursor() as cursor:
            cursor.execute(
                SQL(
                    "SELECT DISTINCT ON(source_data_modified_utc) source_data_modified_utc::TIMESTAMP AT TIME ZONE 'UTC' "
                    "FROM dataflow.metadata WHERE data_id={} ORDER BY source_data_modified_utc DESC"
                ).format(Literal(query.id))
            )
            metadata = cursor.fetchone()
            if not metadata or last_updated_date != metadata[0]:
                cursor.execute(f'SELECT * FROM ({sql}) sq LIMIT 0')
                columns = [
                    (col[0], TYPE_CODES_REVERSED[col[1]]) for col in cursor.description
                ]

                cursor.execute(
                    SQL(
                        "INSERT INTO dataflow.metadata (source_data_modified_utc, table_structure, data_id, data_type)"
                        "VALUES ({},{},{},{})"
                    ).format(
                        Literal(last_updated_date),
                        Literal(json.dumps(columns)),
                        Literal(query.id),
                        Literal(int(DataSetType.DATACUT)),
                    )
                )
