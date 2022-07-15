import json
import logging
import operator
import hashlib
import os
from functools import reduce
from uuid import UUID

import boto3
import botocore
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connections, IntegrityError, transaction
from django.db.models import Q
from django.db.utils import DatabaseError
from django.http import Http404
from django.urls import reverse
from psycopg2.sql import Identifier, Literal, SQL

from dataworkspace.apps.core.utils import close_all_connections_if_not_in_atomic_block
from dataworkspace.apps.core.errors import DatasetUnpublishedError
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    CustomDatasetQueryTable,
    DataSet,
    DataSetSubscription,
    DataSetType,
    Notification,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceTable,
    UserNotification,
    VisualisationCatalogueItem,
    VisualisationLink,
    VisualisationLinkSqlQuery,
)
from dataworkspace.cel import celery_app
from dataworkspace.datasets_db import (
    extract_queried_tables_from_sql_query,
    get_custom_dataset_query_changelog,
    get_data_hash,
    get_reference_dataset_changelog,
    get_source_table_changelog,
    get_earliest_tables_last_updated_date,
)
from dataworkspace.notify import EmailSendFailureException, send_email
from dataworkspace.utils import TYPE_CODES_REVERSED

logger = logging.getLogger("app")


def find_dataset(dataset_uuid, user, model_class=None):
    """
    Attempts to return a dataset given an ID and an optional model class.
    Raises the appropriate exception depending on if the dataset exists/is published
    """
    dataset_models = (
        [ReferenceDataset, DataSet, VisualisationCatalogueItem]
        if not model_class
        else [model_class]
    )
    dataset = None
    for dataset_model in dataset_models:
        id_field = "id" if dataset_model != ReferenceDataset else "uuid"
        try:
            dataset = dataset_model.objects.live().get(**{id_field: dataset_uuid})
        except dataset_model.DoesNotExist:
            pass

    if not dataset:
        raise Http404("No dataset matches the given query.")

    perm = dataset_type_to_manage_unpublished_permission_codename(dataset.type)
    if not dataset.published and not user.has_perm(perm):
        raise DatasetUnpublishedError(dataset)

    return dataset


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    return {
        DataSetType.REFERENCE: "datasets.manage_unpublished_reference_datasets",
        DataSetType.MASTER: "datasets.manage_unpublished_master_datasets",
        DataSetType.DATACUT: "datasets.manage_unpublished_datacut_datasets",
        DataSetType.VISUALISATION: "datasets.manage_unpublished_visualisations",
    }[dataset_type]

#Todo: use the version of this function in core.utils.py and fix circular reference issues.
def _stable_identification_suffix(identifier, short):
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    if short:
        return digest[:8]
    return digest

def get_code_snippets_for_table(request, source_table):
    if not hasattr(source_table, "schema") or not hasattr(source_table, "table"):
        return {"python": "", "r": "", "sql": ""}
    query = get_sql_snippet(source_table.schema, source_table.table, 50)
    sso_id_hex_short = _stable_identification_suffix(str(request.user.profile.sso_id), short=True)
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
        "jupyterlab_link": f"{request.scheme}://jupyterlabpython-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/", 
        "rstudio_link": f"{request.scheme}://rstudio-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/",
    }


def get_code_snippets_for_reference_table(table):
    query = get_sql_snippet("public", table, 50)
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
    }


def get_code_snippets_for_query(request, query):
    sso_id_hex_short = _stable_identification_suffix(str(request.user.profile.sso_id), short=True)
    return {
        "python": get_python_snippet(query),
        "r": get_r_snippet(query),
        "sql": query,
        "jupyterlab_link": f"{request.scheme}://jupyterlab-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/", 
        "rstudio_link": f"{request.scheme}://rstudio-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/",
    }


def get_sql_snippet(schema, table_name, limit=50):
    return f'SELECT * FROM "{schema}"."{table_name}" LIMIT {limit}'


def get_python_snippet(query):
    """
    sqlalchemy.text() is used to make sure the sql string is in a form that sqlalchemy expects.
    `backslash`, `"` and `'''` are also escaped
    """
    query = query.replace("\\", "\\\\").replace('"', '\\"')
    return f"""import pandas
import psycopg2
import sqlalchemy

engine = sqlalchemy.create_engine('postgresql://', execution_options={{"stream_results": True}})
chunks = pandas.read_sql(sqlalchemy.text(\"""{query}\"""), engine, chunksize=10000)
for chunk in chunks:
    display(chunk)"""


def get_r_snippet(query):
    query = query.replace("\\", "\\\\").replace('"', '\\"')
    return f"""library(DBI)
conn <- dbConnect(RPostgres::Postgres())
tryCatch({{
    res <- dbSendQuery(conn, \"{query}\")
    while (!dbHasCompleted(res)) {{
        chunk <- dbFetch(res, n = 50)
        print(chunk)
    }}
    dbClearResult(res)
}}, finally={{
    dbDisconnect(conn)
}})"""


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
            date = get_earliest_tables_last_updated_date(connection_alias, ((schema, table),))
            if date:
                return date
        return None

    account_id = boto3.client("sts").get_caller_identity().get("Account")
    quicksight_client = boto3.client("quicksight")

    logger.info("Fetching last updated dates for QuickSight visualisation links")

    for visualisation_link in VisualisationLink.objects.filter(
        visualisation_type="QUICKSIGHT", visualisation_catalogue_item__deleted=False
    ):
        dashboard_id = visualisation_link.identifier
        logger.info("Fetching last updated date for DashboardId %s", dashboard_id)
        try:
            dashboard = quicksight_client.describe_dashboard(
                AwsAccountId=account_id, DashboardId=dashboard_id
            )["Dashboard"]
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.error("DashboardId %s not found", dashboard_id)
                continue
            raise e
        else:
            data_set_arns = dashboard["Version"]["DataSetArns"]
            logger.info(
                "Found %d DataSets for DashboardId %s",
                len(data_set_arns),
                dashboard_id,
            )
            last_updated_dates = []
            tables = []

            for data_set_arn in data_set_arns:
                try:
                    data_set = quicksight_client.describe_data_set(
                        AwsAccountId=account_id, DataSetId=data_set_arn[50:]
                    )["DataSet"]
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        logger.error("DataSetId %s not found", data_set_arn[50:])
                        continue
                    raise e
                else:
                    logger.info(
                        "Fetching last updated date for %s DataSet %s",
                        data_set["ImportMode"],
                        data_set["DataSetId"],
                    )
                    data_set_last_updated_time = data_set["LastUpdatedTime"]
                    if data_set["ImportMode"] == "SPICE":
                        last_updated_dates.append(data_set_last_updated_time)

                        for table_id, table_map in data_set["PhysicalTableMap"].items():
                            data_set_type = list(table_map)[0]
                            if data_set_type == "CustomSql":
                                store_sql_query(
                                    visualisation_link,
                                    data_set["DataSetId"],
                                    table_id,
                                    table_map["CustomSql"]["SqlQuery"],
                                )
                                tables.extend(
                                    extract_queried_tables_from_sql_query(
                                        table_map["CustomSql"]["SqlQuery"],
                                    )
                                )
                    else:
                        for table_id, table_map in data_set["PhysicalTableMap"].items():
                            data_set_type = list(table_map)[0]
                            if data_set_type == "RelationalTable":
                                last_updated_date_candidate = (
                                    get_last_updated_date_by_table_name(
                                        table_map["RelationalTable"]["Schema"],
                                        table_map["RelationalTable"]["Name"],
                                    )
                                    or data_set_last_updated_time
                                )
                                tables.append(
                                    (
                                        table_map["RelationalTable"]["Schema"],
                                        table_map["RelationalTable"]["Name"],
                                    )
                                )
                            elif data_set_type == "CustomSql":
                                store_sql_query(
                                    visualisation_link,
                                    data_set["DataSetId"],
                                    table_id,
                                    table_map["CustomSql"]["SqlQuery"],
                                )
                                last_updated_date_candidate = max(
                                    dashboard["LastPublishedTime"],
                                    dashboard["LastUpdatedTime"],
                                    data_set["LastUpdatedTime"],
                                )
                                tables.extend(
                                    extract_queried_tables_from_sql_query(
                                        table_map["CustomSql"]["SqlQuery"],
                                    )
                                )
                            elif data_set_type == "S3Source":
                                last_updated_date_candidate = data_set_last_updated_time

                            last_updated_dates.append(last_updated_date_candidate)

            if last_updated_dates:
                logger.info(
                    "Setting last updated date of %s for DashboardId %s",
                    max(last_updated_dates).strftime("%d-%m-%Y %H:%M:%S"),
                    dashboard_id,
                )
                visualisation_link.data_source_last_updated = max(last_updated_dates)
                visualisation_link.save()

            if tables:
                set_dataset_related_visualisation_catalogue_items(visualisation_link, tables)

    logger.info("Finished fetching last updated dates for QuickSight visualisation links")


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
    api_url = os.environ["SUPERSET_ROOT"] + "/api/v1/%s"

    login_response = requests.post(
        api_url % "security/login",
        json={
            "username": os.environ["SUPERSET_DW_USER_USERNAME"],
            "password": os.environ["SUPERSET_DW_USER_PASSWORD"],
            "provider": "db",
        },
    )
    if login_response.status_code != 200:
        logger.error(
            "Unable to authenticate with Superset API with error %s",
            login_response.content,
        )
        return

    jwt_access_token = login_response.json()["access_token"]

    for visualisation_link in VisualisationLink.objects.filter(
        visualisation_type="SUPERSET", visualisation_catalogue_item__deleted=False
    ):
        dashboard_id = int(visualisation_link.identifier)
        logger.info("Setting related visualisations for Superset dashboard id %d", dashboard_id)

        tables = []
        datasets_response = requests.get(
            api_url % f"dashboard/{dashboard_id}/datasets",
            headers={"Authorization": f"Bearer {jwt_access_token}"},
        )
        if datasets_response.status_code != 200:
            logger.error(
                "Unable to get datasets for Superset dashboard id %d with error %s",
                dashboard_id,
                datasets_response.content,
            )
            continue

        datasets = datasets_response.json()["result"]
        logger.info(
            "Found %d datasets for Superset dashboard id %d",
            len(datasets),
            dashboard_id,
        )

        for dataset in datasets:
            logger.info(
                "Extracting tables from dashboard id %d and dataset if %d",
                dashboard_id,
                dataset["id"],
            )

            tables.extend(extract_queried_tables_from_sql_query(dataset["sql"]))

        if tables:
            set_dataset_related_visualisation_catalogue_items(visualisation_link, tables)


def set_dataset_related_visualisation_catalogue_items(visualisation_link, tables):
    datasets = list(
        DataSet.objects.filter(
            reduce(
                operator.or_,
                ([Q(sourcetable__schema=t[0], sourcetable__table=t[1]) for t in tables]),
            )
        )
        .distinct()
        .values_list("id", flat=True)
    )

    datacuts = list(
        CustomDatasetQueryTable.objects.filter(
            reduce(
                operator.or_,
                ([Q(schema=t[0], table=t[1]) for t in tables]),
            )
        )
        .distinct()
        .values_list("query__dataset__id", flat=True)
    )

    for object_id in datasets + datacuts:
        visualisation_link.visualisation_catalogue_item.datasets.add(object_id)


def build_filtered_dataset_query(inner_query, column_config, params):
    column_map = {x["field"]: x for x in column_config}
    query_params = {
        "offset": int(params.get("start", 0)),
        "limit": params.get("limit"),
    }
    sort_dir = "DESC" if params.get("sortDir", "").lower() == "desc" else "ASC"
    sort_fields = [column_config[0]["field"]]
    if params.get("sortField") and params.get("sortField") in column_map:
        sort_fields = [params.get("sortField")]

    where_clause = []
    for field, filter_data in params.get("filters", {}).items():
        terms = [filter_data.get("filter"), filter_data.get("filterTo")]
        if filter_data["filterType"] == "date":
            terms = [filter_data["dateFrom"], filter_data["dateTo"]]

        if field in column_map:
            data_type = column_map[field].get("dataType", filter_data["filterType"])

            # Searching on invalid uuids will raise an exception.
            # To get around that, if the uuid is invalid we
            # force the query to return no results (`where 1 = 2`)
            if data_type == "uuid":
                try:
                    UUID(terms[0], version=4)
                except ValueError:
                    where_clause.append(SQL("1 = 2"))
                    break

            # Booleans are passed as integers
            if data_type == "boolean":
                terms[0] = bool(int(terms[0]))

            # Arrays are a special case
            if data_type == "array":
                if filter_data["type"] == "contains":
                    query_params[field] = terms[0]
                    where_clause.append(
                        SQL(f"LOWER(%({field})s::TEXT) = ANY(LOWER({{}}::TEXT)::TEXT[])").format(
                            Identifier(field)
                        )
                    )
                if filter_data["type"] == "notContains":
                    query_params[field] = terms[0]
                    where_clause.append(
                        SQL(
                            f"NOT LOWER(%({field})s::TEXT) = ANY(LOWER({{}}::TEXT)::TEXT[]) or {{}} is NULL"
                        ).format(Identifier(field), Identifier(field))
                    )
                if filter_data["type"] == "equals":
                    query_params[field] = ",".join(
                        [x.rstrip().lstrip() for x in terms[0].split(",")]
                    )
                    where_clause.append(
                        SQL(
                            f"LOWER(STRING_TO_ARRAY(%({field})s, ',')::text) = LOWER({{}}::TEXT)"
                        ).format(Identifier(field))
                    )
                if filter_data["type"] == "notEqual":
                    query_params[field] = ",".join(
                        [x.rstrip().lstrip() for x in terms[0].split(",")]
                    )
                    where_clause.append(
                        SQL(
                            f"LOWER(STRING_TO_ARRAY(%({field})s, ',')::text) != LOWER({{}}::TEXT) or {{}} is NULL"
                        ).format(Identifier(field), Identifier(field))
                    )

            elif data_type == "text" and filter_data["type"] == "contains":
                query_params[field] = f"%{terms[0]}%"
                where_clause.append(
                    SQL(f"lower({{}}) LIKE lower(%({field})s)").format(Identifier(field))
                )
            elif data_type == "text" and filter_data["type"] == "notContains":
                query_params[field] = f"%{terms[0]}%"
                where_clause.append(
                    SQL(f"lower({{}}) NOT LIKE lower(%({field})s)").format(Identifier(field))
                )
            elif filter_data["type"] == "equals":
                query_params[field] = terms[0]
                if data_type == "text":
                    where_clause.append(
                        SQL(f"lower({{}}) = lower(%({field})s)").format(Identifier(field))
                    )
                else:
                    where_clause.append(SQL(f"{{}} = %({field})s").format(Identifier(field)))

            elif filter_data["type"] == "notEqual":
                query_params[field] = terms[0]
                if data_type == "text":
                    where_clause.append(
                        SQL(f"lower({{}}) != lower(%({field})s)").format(Identifier(field))
                    )
                else:
                    where_clause.append(
                        SQL(f"{{}} is distinct from %({field})s").format(Identifier(field))
                    )
            elif filter_data["type"] in ["startsWith", "endsWith"]:
                query_params[field] = (
                    f"{terms[0]}%" if filter_data["type"] == "startsWith" else f"%{terms[0]}"
                )
                where_clause.append(
                    SQL(f"lower({{}}) LIKE lower(%({field})s)").format(Identifier(field))
                )
            elif filter_data["type"] == "inRange":
                where_clause.append(
                    SQL(f"{{}} BETWEEN %({field}_from)s AND %({field}_to)s").format(
                        Identifier(field)
                    )
                )
                query_params[f"{field}_from"] = terms[0]
                query_params[f"{field}_to"] = terms[1]
            elif filter_data["type"] in ["greaterThan", "greaterThanOrEqual"]:
                operator = ">" if filter_data["type"] == "greaterThan" else ">="
                where_clause.append(SQL(f"{{}} {operator} %({field})s").format(Identifier(field)))
                query_params[field] = terms[0]
            elif filter_data["type"] in ["lessThan", "lessThanOrEqual"]:
                query_params[field] = terms[0]
                operator = "<" if filter_data["type"] == "lessThan" else "<="
                where_clause.append(SQL(f"{{}} {operator} %({field})s").format(Identifier(field)))

    if where_clause:
        where_clause = SQL("WHERE") + SQL(" AND ").join(where_clause)
    query = SQL(
        f"""
        SELECT {{}}
        FROM ({{}}) a
        {{}}
        ORDER BY {{}} {sort_dir}
        LIMIT %(limit)s
        OFFSET %(offset)s
        """
    ).format(
        SQL(",").join(map(Identifier, column_map)),
        inner_query,
        SQL(" ").join(where_clause),
        SQL(",").join(map(Identifier, sort_fields)),
    )

    return query, query_params


def _get_detailed_changelog(changelog, initial_change_type):
    for record in changelog:
        if not record["previous_table_structure"] and not record["previous_data_hash"]:
            record["summary"] = initial_change_type
        elif record["previous_table_name"] != record["table_name"]:
            record["summary"] = f"Table renamed from {record['previous_table_name']}"
        elif record["previous_table_structure"] != record["table_structure"]:
            column_names = [c[0] for c in record["table_structure"]]
            previous_column_names = [c[0] for c in record["previous_table_structure"]]
            a = list(set(column_names) - set(previous_column_names))
            b = list(set(previous_column_names) - set(column_names))
            if not a and not b:
                record["summary"] = "N/A"
                continue

            record["summary"] = (
                (
                    f'Column{"s" if len(a) > 1 else ""} {" and ".join(a)} {"were" if len(a) > 1 else "was"} added'
                    if a
                    else ""
                )
                + (", " if a and b else "")
                + (
                    f'Column{"s" if len(b) > 1 else ""} {" and ".join(b)} {"were" if len(b) > 1 else "was"} removed'
                    if b
                    else ""
                )
            )
        elif record["previous_data_hash"] != record["data_hash"]:
            record["summary"] = "Records in the dataset changed"
        else:
            record["summary"] = "N/A"
    return changelog


def get_detailed_changelog(related_object):
    if isinstance(related_object, SourceTable):
        return _get_detailed_changelog(
            get_source_table_changelog(related_object),
            "Table creation",
        )
    elif isinstance(related_object, CustomDatasetQuery):
        return _get_detailed_changelog(
            get_custom_dataset_query_changelog(related_object),
            "Query creation",
        )
    elif isinstance(related_object, ReferenceDataset):
        return _get_detailed_changelog(
            get_reference_dataset_changelog(related_object),
            "Reference dataset creation",
        )
    return []


def get_change_item(related_object, change_id):
    changelog = get_detailed_changelog(related_object)
    for change in changelog:
        if change["change_id"] == change_id:
            return change

    logger.warning("No match for get_change_item %s type: %s", change_id, type(change_id))
    logger.warning(related_object)
    logger.warning(changelog)

    return None


@celery_app.task()
def update_metadata_with_source_table_id():
    database_name = list(settings.DATABASES_DATA.items())[0][0]
    with connections[database_name].cursor() as cursor:
        cursor.execute(
            SQL(
                "SELECT id,table_schema,table_name "
                "FROM dataflow.metadata "
                "WHERE data_type={} "
                "AND data_ids IS NULL"
            ).format(Literal(DataSetType.MASTER))
        )
        metadata = cursor.fetchall()

        for metadata_id, schema, table in metadata:
            source_tables = list(
                SourceTable.objects.filter(schema=schema, table=table).values_list("id", flat=True)
            )
            if not source_tables:
                continue
            cursor.execute(
                SQL("UPDATE dataflow.metadata SET data_ids ={} WHERE id={}").format(
                    Literal(source_tables),
                    Literal(metadata_id),
                )
            )


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def store_custom_dataset_query_metadata():
    with cache.lock("store_custom_dataset_query_metadata_lock", blocking_timeout=0, timeout=86400):
        do_store_custom_dataset_query_metadata()


def do_store_custom_dataset_query_metadata():
    statement_timeout = 60 * 1000
    for query in CustomDatasetQuery.objects.filter(dataset__published=True):
        sql = query.query.rstrip().rstrip(";")

        tables = extract_queried_tables_from_sql_query(sql)
        if not tables:
            logger.info(
                "Not adding metadata for query %s as no tables could be extracted", query.name
            )
            continue

        tables_last_updated_date = get_earliest_tables_last_updated_date(
            query.database.memorable_name, tuple(tables)
        )
        query_last_updated_date = query.modified_date

        last_updated_date = (
            max(tables_last_updated_date, query_last_updated_date)
            if tables_last_updated_date
            else query_last_updated_date
        )
        with connections[query.database.memorable_name].cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {statement_timeout}")
            cursor.execute(
                SQL(
                    "SELECT DISTINCT ON(source_data_modified_utc) "
                    "source_data_modified_utc::TIMESTAMP AT TIME ZONE 'UTC' "
                    "FROM dataflow.metadata "
                    "WHERE {} =ANY(data_ids) "
                    "AND data_type = {} "
                    "ORDER BY source_data_modified_utc DESC"
                ).format(
                    Literal(str(query.id)),
                    Literal(int(DataSetType.DATACUT)),
                )
            )
            metadata = cursor.fetchone()
            if not metadata or last_updated_date != metadata[0]:
                try:
                    data_hash = get_data_hash(cursor, sql)
                except DatabaseError as e:
                    logger.error(
                        "Not adding metadata for query %s as get_data_hash failed with %s",
                        query.name,
                        e,
                    )
                    continue

                try:
                    cursor.execute(f"SELECT * FROM ({sql}) sq LIMIT 0")
                except DatabaseError as e:
                    logger.error(
                        "Not adding metadata for query %s as querying for columns failed with %s",
                        query.name,
                        e,
                    )
                    continue

                columns = [(col[0], TYPE_CODES_REVERSED[col[1]]) for col in cursor.description]

                cursor.execute(
                    SQL(
                        "INSERT INTO dataflow.metadata"
                        "(source_data_modified_utc, table_structure, data_hash_v1, data_ids, data_type)"
                        "VALUES ({},{},{},{},{})"
                    ).format(
                        Literal(last_updated_date),
                        Literal(json.dumps(columns)),
                        Literal(data_hash),
                        Literal([str(query.id)]),
                        Literal(int(DataSetType.DATACUT)),
                    )
                )


@celery_app.task()
def store_reference_dataset_metadata():
    for reference_dataset in ReferenceDataset.objects.live().filter(published=True):
        logger.info(
            "Checking for metadata update for reference dataset '%s'", reference_dataset.name
        )

        # Get the update date from reference dataset
        latest_update_date = reference_dataset.modified_date

        # Get the latest modified date from this reference dataset's fields
        latest_update_date = max(
            reference_dataset.fields.latest("modified_date").modified_date, latest_update_date
        )

        # Get the latest date the data in this dataset was updated
        data_updated = reference_dataset.data_last_updated
        if data_updated:
            latest_update_date = max(latest_update_date, data_updated)

        # Get the latest data updated dates for any linked reference datasets
        linked_datasets_updated_dates = [
            field.linked_reference_dataset_field.reference_dataset.data_last_updated
            for field in reference_dataset.fields.filter(
                data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            )
        ]
        if linked_datasets_updated_dates:
            latest_update_date = max(latest_update_date, max(linked_datasets_updated_dates))

        logger.info(
            "Latest update date for reference dataset '%s' is %s",
            reference_dataset.name,
            latest_update_date,
        )

        # Get the latest metadata record
        db_name = list(settings.DATABASES_DATA.items())[0][0]
        with connections[db_name].cursor() as cursor:
            cursor.execute(
                SQL(
                    "SELECT DISTINCT ON(source_data_modified_utc)"
                    "source_data_modified_utc::TIMESTAMP AT TIME ZONE 'UTC' "
                    "FROM dataflow.metadata "
                    "WHERE {} = any(data_ids) "
                    "AND data_type = {} "
                    "ORDER BY source_data_modified_utc DESC"
                ).format(
                    Literal(str(reference_dataset.id)),
                    Literal(int(DataSetType.REFERENCE)),
                )
            )
            metadata = cursor.fetchone()

            # If the metadata record is older than our latest updated date write a new record
            if not metadata or latest_update_date > metadata[0]:
                logger.info(
                    "Creating new metadata record for reference dataset '%s'",
                    reference_dataset.name,
                )

                columns = [
                    (
                        field.relationship_name
                        if field.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
                        else field.column_name,
                        field.get_postgres_datatype(),
                    )
                    for field in reference_dataset.fields.all()
                ]
                cursor.execute(
                    SQL(
                        """
                        INSERT INTO dataflow.metadata (
                            source_data_modified_utc,
                            table_schema,
                            table_name,
                            table_structure,
                            data_hash_v1,
                            data_type,
                            data_ids
                        )
                        VALUES ({},'public', {}, {}, {}, {}, {})
                        """
                    ).format(
                        Literal(latest_update_date),
                        Literal(reference_dataset.table_name),
                        Literal(json.dumps(columns)),
                        Literal(reference_dataset.get_metadata_table_hash()),
                        Literal(int(DataSetType.REFERENCE)),
                        Literal([reference_dataset.id]),
                    )
                )
            else:
                logger.info(
                    "Not creating a metadata record for %s as the last updated date is before %s",
                    reference_dataset.name,
                    metadata[0],
                )


@celery_app.task()
def send_notification_emails():
    """
    Rules are:

    Signed up for schema changes, there was a schema change, will get an email
    Signed up for schema changes, there was a data change with no schema change, will not get an email
    Signed up for schema changes, there was no change, will not get an email
    Signed up for all changes, there was a schema change, will get an email
    Signed up for all changes, there was a data change with no schema change, will get an email
    Signed up for all changes, there was no change, will not get an email
    Signed up for no changes, there was a schema change, will not get an email
    Signed up for no changes, there was a data change with no schema change, will not get an email
    Signed up for no changes, there was no change, will not get an email
    """

    def create_notifications():
        logger.info("Creating notifications")
        for notifiable_object in (
            list(SourceTable.objects.order_by("id"))
            + list(CustomDatasetQuery.objects.order_by("id"))
            + list(ReferenceDataset.objects.order_by("id"))
        ):
            logger.info(
                "Creating notification for %s %s", type(notifiable_object), notifiable_object.id
            )
            changelog = get_detailed_changelog(notifiable_object)
            if len(changelog) == 0:
                logger.info(
                    "No changelog records found for %s %s",
                    type(notifiable_object),
                    notifiable_object.id,
                )
                continue

            # For now only notify about the most recent change
            change = changelog[0]
            schema_change = (change["previous_table_structure"] != change["table_structure"]) or (
                change["previous_table_name"] != change["table_name"]
            )
            data_change = change["previous_data_hash"] != change["data_hash"]

            notification, created = Notification.objects.get_or_create(
                changelog_id=change["change_id"],
                defaults={"related_object": notifiable_object},
            )
            if created:
                dataset = (
                    notifiable_object
                    if isinstance(notifiable_object, ReferenceDataset)
                    else notifiable_object.dataset
                )
                logger.info(
                    "Processing notifications for dataset %s",
                    dataset.name,
                )
                queryset = DataSetSubscription.objects.none()
                queryset = (
                    dataset.subscriptions.filter(notify_on_schema_change=True)
                    if schema_change
                    else dataset.subscriptions.filter(notify_on_data_change=True)
                    if data_change
                    else DataSetSubscription.objects.none()
                )

                for subscription in queryset:
                    UserNotification.objects.create(
                        notification=notification,
                        subscription=subscription,
                    )
            else:
                logger.info(
                    "Notification already exists for change_id %s, skipping", change["change_id"]
                )

    def send_notifications():
        user_notification_ids = list(
            UserNotification.objects.filter(email_id=None).values_list("id", flat=True)
        )

        for user_notification_id in user_notification_ids:
            try:
                with transaction.atomic():
                    user_notification = UserNotification.objects.select_for_update().get(
                        id=user_notification_id
                    )
                    user_notification.refresh_from_db()
                    if user_notification.email_id is not None:
                        # This means another task has updated the email_id field since
                        # the filter above was executed
                        continue

                    change = get_change_item(
                        user_notification.notification.related_object,
                        user_notification.notification.changelog_id,
                    )

                    if not change:
                        logger.error("get_change_item returned None")

                    change_date = change["change_date"]

                    if (change["previous_table_structure"] != change["table_structure"]) or (
                        change["previous_table_name"] != change["table_name"]
                    ):
                        template_id = settings.NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID
                    elif change["previous_data_hash"] != change["data_hash"]:
                        template_id = settings.NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID

                    email_address = user_notification.subscription.user.email
                    dataset_name = user_notification.subscription.dataset.name
                    dataset_url = (
                        os.environ["APPLICATION_ROOT_DOMAIN"]
                        + user_notification.subscription.dataset.get_absolute_url()
                    )
                    manage_subscriptions_url = os.environ["APPLICATION_ROOT_DOMAIN"] + reverse(
                        "datasets:email_preferences"
                    )
                    logger.info(
                        "Sending notification about dataset %s changing structure at %s to user %s",
                        dataset_name,
                        change_date,
                        email_address,
                    )
                    try:
                        email_id = send_email(
                            template_id,
                            email_address,
                            personalisation={
                                "change_date": change_date.strftime("%d/%m/%Y - %H:%M:%S"),
                                "dataset_name": dataset_name,
                                "dataset_url": dataset_url,
                                "manage_subscriptions_url": manage_subscriptions_url,
                                "summary": change["summary"],
                            },
                        )
                    except EmailSendFailureException:
                        logger.exception("Failed to send email")
                    else:
                        user_notification.email_id = email_id
                        user_notification.save(update_fields=["email_id"])
            except IntegrityError as e:
                logger.error("Exception when sending notifications: %s", e)

    try:
        with transaction.atomic():
            create_notifications()
    except IntegrityError as e:
        logger.error("Exception when creating notifications: %s", e)
    else:
        send_notifications()


def get_dataset_table(obj):
    datasets = set()
    for table in obj.tables.all():
        for source_table in SourceTable.objects.filter(dataset__deleted=False).filter(
            schema=table.schema, table=table.table
        ):
            datasets.add(source_table.dataset)
        if table.schema == "public":
            for ref_dataset in ReferenceDataset.objects.live().filter(table_name=table.table):
                datasets.add(ref_dataset)
    return datasets
