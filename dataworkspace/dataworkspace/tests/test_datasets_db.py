import datetime

import pytest
import pytz

from dataworkspace.datasets_db import (
    extract_queried_tables_from_sql_query,
    get_earliest_tables_last_updated_date,
)


@pytest.mark.parametrize(
    "query, expected_tables",
    (
        ("SELECT * FROM auth_user", [("public", "auth_user")]),
        ("SELECT * FROM auth_user;", [("public", "auth_user")]),
        (
            "SELECT * FROM auth_user JOIN auth_user_groups ON auth_user.id = auth_user_groups.user_id",
            [("public", "auth_user"), ("public", "auth_user_groups")],
        ),
        (
            "WITH foo as (SELECT * FROM auth_user) SELECT * FROM foo",
            [("public", "auth_user")],
        ),
        ("SELECT 1", []),
        ("SELECT * FROM test", [("public", "test")]),
        ("SELECT * FROM", []),
        (
            'SELECT * FROM "schema.with.dots"."table.with.dots"',
            [("schema.with.dots", "table.with.dots")],
        ),
        (
            "WITH my_cte AS (SELECT * FROM my_real) SELECT * FROM my_cte",
            [("public", "my_real")],
        ),
        (
            "WITH my_cte AS (SELECT * FROM my_schema.my_real) SELECT * FROM my_cte",
            [("my_schema", "my_real")],
        ),
        (
            "WITH my_real AS (SELECT * FROM my_real) SELECT * FROM my_real",
            [("public", "my_real")],
        ),
        (
            "WITH my_real AS (SELECT * FROM my_schema.my_real) SELECT * FROM my_real",
            [("my_schema", "my_real")],
        ),
        (
            "SELECT (SELECT * FROM my_inner)",
            [("public", "my_inner")],
        ),
        (
            "SELECT (WITH my_cte AS (SELECT * FROM my_inner) SELECT * FROM my_cte)",
            [("public", "my_inner")],
        ),
        (
            """
                SELECT (
                    WITH
                        my_cte_1 AS (SELECT * FROM my_inner),
                        my_cte_2 AS (SELECT * FROM my_cte_1)
                    SELECT * FROM my_cte_1
                )
            """,
            [("public", "my_inner")],
        ),
        (
            """
                SELECT (
                    WITH
                        my_cte_1 AS (SELECT * FROM my_inner_1),
                        my_cte_2 AS (SELECT * FROM my_inner_2)
                    SELECT * FROM my_cte_1
                )
            """,
            [("public", "my_inner_1"), ("public", "my_inner_2")],
        ),
        (
            """
                SELECT (
                    WITH
                        my_cte_1 AS (SELECT * FROM my_inner_1),
                        my_inner_2 AS (SELECT * FROM my_inner_2)
                    SELECT * FROM my_cte_1
                )
            """,
            [("public", "my_inner_1"), ("public", "my_inner_2")],
        ),
    ),
)
def test_sql_query_tables_extracted_correctly(query, expected_tables):
    tables = extract_queried_tables_from_sql_query(query)
    assert tables == expected_tables


@pytest.mark.django_db
def test_get_table_last_updated_date_with_source_data_modified_metadata(metadata_db):
    assert get_earliest_tables_last_updated_date(
        "my_database", (("public", "table2"),)
    ) == datetime.datetime(2020, 9, 1, 0, 1).replace(tzinfo=pytz.UTC)


@pytest.mark.django_db
def test_get_table_last_updated_date_with_dataflow_swapped_table_metadata(metadata_db):
    assert get_earliest_tables_last_updated_date(
        "my_database", (("public", "table4"),)
    ) == datetime.datetime(2021, 12, 1, 0, 0).replace(tzinfo=pytz.UTC)
