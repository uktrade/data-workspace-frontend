import pytest

from dataworkspace.datasets_db import extract_queried_tables_from_sql_query


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
        ("SELECT * FROM test", []),
        ("SELECT * FROM", []),
    ),
)
@pytest.mark.django_db
def test_sql_query_tables_extracted_correctly(query, expected_tables):
    tables = extract_queried_tables_from_sql_query("test_external_db", query)
    assert tables == expected_tables
