import logging
import uuid
from time import time

from contextlib import contextmanager
from datetime import timedelta

import psycopg2
import sqlparse

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import DatabaseError

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    new_private_database_credentials,
    source_tables_for_user,
    db_role_schema_suffix_for_user,
    postgres_user,
)
from dataworkspace.apps.explorer.models import QueryLog


logger = logging.getLogger('app')
EXPLORER_PARAM_TOKEN = "$$"


def param(name):
    return "%s%s%s" % (EXPLORER_PARAM_TOKEN, name, EXPLORER_PARAM_TOKEN)


def safe_login_prompt(request):
    defaults = {
        'template_name': 'admin/login.html',
        'authentication_form': AuthenticationForm,
        'extra_context': {
            'title': 'Log in',
            'app_path': request.get_full_path(),
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
    val = request.GET.get('params', None)
    try:
        d = {}
        tuples = val.split('|')
        for t in tuples:
            res = t.split(':')
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
    return get_int_from_request(request, 'query_id', None)


def url_get_log_id(request):
    return get_int_from_request(request, 'querylog_id', None)


def url_get_show(request):
    return bool(get_int_from_request(request, 'show', 1))


def url_get_save(request):
    return bool(get_int_from_request(request, 'save', 0))


def url_get_params(request):
    return get_params_from_request(request)


def fmt_sql(sql):
    return sqlparse.format(sql, reindent=True, keyword_case='upper')


def noop_decorator(f):
    return f


class InvalidExplorerConnectionException(Exception):
    pass


def user_cached_credentials_key(user):
    return f"explorer_credentials_{user.profile.sso_id}"


def get_user_explorer_connection_settings(user, alias):
    from dataworkspace.apps.explorer.connections import (  # pylint: disable=import-outside-toplevel
        connections,
    )

    if not alias:
        alias = settings.EXPLORER_DEFAULT_CONNECTION

    if alias not in connections:
        raise InvalidExplorerConnectionException(
            'Attempted to access connection %s, but that is not a registered Explorer connection.'
            % alias
        )

    def get_available_user_connections(_user_credentials):
        return {data['memorable_name']: data for data in _user_credentials}

    with cache.lock(
        f'get-explorer-connection-{user.profile.sso_id}',
        blocking_timeout=30,
        timeout=180,
    ):
        cache_key = user_cached_credentials_key(user)
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
            db_role_schema_suffix = db_role_schema_suffix_for_user(user)
            source_tables = source_tables_for_user(user)
            db_user = postgres_user(user.email, suffix='explorer')
            duration = timedelta(hours=24)
            cache_duration = (duration - timedelta(minutes=15)).total_seconds()

            user_credentials = new_private_database_credentials(
                db_role_schema_suffix,
                source_tables,
                db_user,
                valid_for=duration,
                force_create_for_databases=Database.objects.filter(
                    memorable_name__in=connections.keys()
                ).all(),
            )
            cache.set(cache_key, user_credentials, timeout=cache_duration)

    db_aliases_to_credentials = get_available_user_connections(user_credentials)
    if alias not in db_aliases_to_credentials:
        raise RuntimeError(
            f"The credentials for {user.email} did not include any for the `{alias}` database."
        )

    return db_aliases_to_credentials[alias]


@contextmanager
def user_explorer_connection(connection_settings):
    with psycopg2.connect(
        dbname=connection_settings['db_name'],
        host=connection_settings['db_host'],
        user=connection_settings['db_user'],
        password=connection_settings['db_password'],
        port=connection_settings['db_port'],
    ) as conn:
        yield conn


def get_total_pages(total_rows, page_size):
    if not total_rows or not page_size:
        return 1
    remainder = total_rows % page_size
    if remainder:
        remainder = 1
    return int(total_rows / page_size) + remainder


def remove_data_explorer_user_cached_credentials(user):
    logger.info("Clearing Data Explorer cached credentials for %s", user)
    cache_key = user_cached_credentials_key(user)
    cache.delete(cache_key)


class QueryResult:
    def __init__(
        self, sql, page, limit, timeout, duration, description, data, row_count
    ):
        self.sql = sql
        self.page = page
        self.limit = limit
        self.timeout = timeout
        self.duration = duration
        self.description = description
        self.data = data
        self.row_count = row_count

    @property
    def header_strings(self):
        return [str(h) for h in self.headers]

    @property
    def headers(self):
        return (
            [ColumnHeader(d[0]) for d in self.description]
            if self.description
            else [ColumnHeader('--')]
        )

    def column(self, ix):
        return [r[ix] for r in self.data]


class ColumnHeader:
    def __init__(self, title):
        self.title = title.strip()

    def __str__(self):
        return self.title


def execute_query(query, user, page, limit, timeout, log_query):
    user_connection_settings = get_user_explorer_connection_settings(
        user, query.connection
    )
    with user_explorer_connection(user_connection_settings) as conn:
        cursor = conn.cursor()
        cursor_name = 'cur_%s' % str(uuid.uuid4()).replace('-', '')[:10]

        start_time = time()
        try:
            cursor.execute(f'SET statement_timeout = {timeout}')
            cursor.execute(
                f'DECLARE {cursor_name} CURSOR WITH HOLD FOR {query.final_sql()}'
            )
            if page and page > 1:
                offset = (page - 1) * limit
                cursor.execute(f'MOVE {offset} FROM {cursor_name}')
            cursor.execute(f'FETCH {limit} FROM {cursor_name}')
        except DatabaseError as e:
            raise e

        duration = (time() - start_time) * 1000
        description = cursor.description or []
        data = [list(r) for r in cursor]
        cursor.execute(f'CLOSE {cursor_name}')

        sql = query.final_sql().rstrip().rstrip(';')
        cursor.execute(f'select count(*) from ({sql}) t')
        row_count = cursor.fetchone()[0]

    if log_query:
        QueryLog.objects.create(
            sql=query.final_sql(),
            query_id=query.id,
            run_by_user=user,
            connection=query.connection,
            duration=duration,
        )

    return QueryResult(
        query.final_sql(), page, limit, timeout, duration, description, data, row_count
    )
