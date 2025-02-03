import json
import logging
import re
from contextlib import contextmanager
from datetime import timedelta

import psycopg2
import sqlparse
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    close_admin_db_connection_if_not_in_atomic_block,
    db_role_schema_suffix_for_user,
    new_private_database_credentials,
    postgres_user,
    source_tables_for_user,
)
from dataworkspace.apps.explorer.models import QueryLog

logger = logging.getLogger("app")
EXPLORER_PARAM_TOKEN = "$$"


def param(name):
    return "%s%s%s" % (EXPLORER_PARAM_TOKEN, name, EXPLORER_PARAM_TOKEN)


def safe_login_prompt(request):
    defaults = {
        "template_name": "admin/login.html",
        "authentication_form": AuthenticationForm,
        "extra_context": {
            "title": "Log in",
            "app_path": request.get_full_path(),
            REDIRECT_FIELD_NAME: request.get_full_path(),
        },
    }
    return LoginView.as_view(**defaults)(request)


def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except ValueError:
        return default


def get_int_from_request(request, name, default):
    val = request.GET.get(name, default)
    return safe_cast(val, int, default) if val else None


def get_params_from_request(request):
    val = request.GET.get("params", None)
    try:
        d = {}
        tuples = val.split("|")
        for t in tuples:
            res = t.split(":")
            d[res[0]] = res[1]
        return d
    except Exception:  # pylint: disable=broad-except
        return None


def url_get_rows(request):
    rows = request.POST.get("query-rows", str(settings.EXPLORER_DEFAULT_ROWS))
    if not rows.isnumeric():
        return settings.EXPLORER_DEFAULT_ROWS
    return int(rows)


def url_get_page(request):
    page = request.POST.get("query-page", "1")
    if not page.isnumeric():
        return 1
    return int(page)


def url_get_query_id(request):
    return get_int_from_request(request, "query_id", None)


def url_get_log_id(request):
    return get_int_from_request(request, "querylog_id", None)


def url_get_show(request):
    return bool(get_int_from_request(request, "show", 1))


def url_get_save(request):
    return bool(get_int_from_request(request, "save", 0))


def url_get_params(request):
    return get_params_from_request(request)


def fmt_sql(sql):
    return sqlparse.format(sql, reindent=True, keyword_case="upper")


def noop_decorator(f):
    return f


class InvalidExplorerConnectionException(Exception):
    pass


class QueryException(Exception):
    pass


credentials_version_key = "explorer_credentials_version"


def get_user_cached_credentials_key(user):
    # Set to never expire as reverting to a previous version will cause
    # potentially invalid cached credentials to be used if the user loses
    # or gains access to a dashboard
    cache.set(credentials_version_key, 1, nx=True, timeout=None)
    credentials_version = cache.get(credentials_version_key, None)
    return f"explorer_credentials_{credentials_version}_{user.profile.sso_id}"


def get_user_explorer_connection_settings(user, alias):
    from dataworkspace.apps.explorer.connections import (  # pylint: disable=import-outside-toplevel
        connections,
    )

    if not alias:
        alias = settings.EXPLORER_DEFAULT_CONNECTION

    if alias not in connections:
        raise InvalidExplorerConnectionException(
            "Attempted to access connection %s, but that is not a registered Explorer connection."
            % alias
        )

    def get_available_user_connections(_user_credentials):
        return {data["memorable_name"]: data for data in _user_credentials}

    user_profile_sso_id = user.profile.sso_id
    close_admin_db_connection_if_not_in_atomic_block()
    cache_key = get_user_cached_credentials_key(user)
    user_credentials = cache.get(cache_key, None)

    # Make sure that the connection settings are still valid
    if user_credentials:
        db_aliases_to_credentials = get_available_user_connections(user_credentials)
        try:
            with user_explorer_connection(db_aliases_to_credentials[alias]):
                pass
        except psycopg2.OperationalError:
            logger.exception(
                "Unable to connect using existing cached explorer credentials for %s",
                user,
            )
            user_credentials = None

    if not user_credentials:
        with cache.lock(
            f"get-explorer-connection-{user_profile_sso_id}",
            blocking_timeout=30,
            timeout=180,
        ):
            # There is a chance that a parallel request created new credentials. If so, we don't
            # want to create credentials again since they are almost definitely still valid
            user_credentials = cache.get(cache_key, None)

            if not user_credentials:
                db_role_schema_suffix = db_role_schema_suffix_for_user(user)
                source_tables = source_tables_for_user(user)
                db_user = postgres_user(user.email, suffix="explorer")
                duration = timedelta(hours=24)
                cache_duration = (duration - timedelta(minutes=15)).total_seconds()

                user_credentials = new_private_database_credentials(
                    db_role_schema_suffix,
                    source_tables,
                    db_user,
                    user,
                    valid_for=duration,
                    force_create_for_databases=list(connections.keys()),
                )
                cache.set(cache_key, user_credentials, timeout=cache_duration)

    db_aliases_to_credentials = get_available_user_connections(user_credentials)
    if alias not in db_aliases_to_credentials:
        raise RuntimeError(
            f"The credentials for {user.email} did not include any for the `{alias}` database."
        )

    return db_aliases_to_credentials[alias]


def remove_data_explorer_user_cached_credentials(user):
    cache_key = get_user_cached_credentials_key(user)
    cache.delete(cache_key)


def invalidate_data_explorer_user_cached_credentials():
    credentials_version = cache.get(credentials_version_key, None)
    if credentials_version:
        cache.incr(credentials_version_key)


@contextmanager
def user_explorer_connection(connection_settings):
    with psycopg2.connect(
        dbname=connection_settings["db_name"],
        host=connection_settings["db_host"],
        user=connection_settings["db_user"],
        password=connection_settings["db_password"],
        port=connection_settings["db_port"],
    ) as conn:
        yield conn


def get_total_pages(total_rows, page_size):
    if not total_rows or not page_size:
        return 1
    remainder = total_rows % page_size
    if remainder:
        remainder = 1
    return int(total_rows / page_size) + remainder


def tempory_query_table_name(user, query_log_id):
    schema_name = f"{USER_SCHEMA_STEM}{db_role_schema_suffix_for_user(user)}"
    return f"{schema_name}._data_explorer_tmp_query_{query_log_id}"


def fetch_query_results(query_log_id):
    query_log = get_object_or_404(QueryLog, pk=query_log_id)

    user = query_log.run_by_user
    user_connection_settings = get_user_explorer_connection_settings(user, query_log.connection)
    table_name = tempory_query_table_name(user, query_log.id)
    with user_explorer_connection(user_connection_settings) as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute("select oid from pg_type where typname='jsonb'")
        jsonb_code = cursor.fetchone()[0]

        cursor.execute(f"SELECT * FROM {table_name}")
        # strip the prefix from the results
        description = [(re.sub(r"col_\d*_", "", s.name),) for s in cursor.description]
        headers = [d[0].strip() for d in description] if description else ["--"]
        data_list = [list(r) for r in cursor]
        types = ["jsonb" if t.type_code == jsonb_code else None for t in cursor.description]
        data = [
            [
                json.dumps(row, indent=2) if types[i] == "jsonb" else row
                for i, row in enumerate(record)
            ]
            for record in data_list
        ]
    return headers, data, query_log
