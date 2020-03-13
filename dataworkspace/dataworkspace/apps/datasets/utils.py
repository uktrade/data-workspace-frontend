from django.http import Http404
from django.shortcuts import get_object_or_404

from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.constants import DataSetType


def find_dataset(dataset_uuid, user):
    dataset = get_object_or_404(DataSet.objects.live(), id=dataset_uuid)

    if user.has_perm(
        dataset_type_to_manage_unpublished_permission_codename(dataset.type)
    ):
        return dataset

    if not dataset.published:
        raise Http404('No dataset matches the given query.')

    return dataset


def dataset_type_to_manage_unpublished_permission_codename(dataset_type: int):
    return {
        DataSetType.REFERENCE.value: 'datasets.manage_unpublished_reference_datasets',
        DataSetType.MASTER.value: 'datasets.manage_unpublished_master_datasets',
        DataSetType.DATACUT.value: 'datasets.manage_unpublished_datacut_datasets',
    }[dataset_type]


def get_code_snippets(dataset: DataSet):
    sourcetables = dataset.sourcetable_set.all()
    if not sourcetables:
        return {}

    schema, table_name = sourcetables[0].schema, sourcetables[0].table
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

    sql_snippet = f"""SELECT * FROM "{schema}"."{table_name}" LIMIT 50"""

    return {"python": python_snippet, "r": r_snippet, "sql": sql_snippet}
