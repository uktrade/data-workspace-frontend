import logging
import re
from contextlib import contextmanager
from datetime import timedelta

import psycopg2
import sqlparse
from six import text_type

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    new_private_database_credentials,
    source_tables_for_user,
    db_role_schema_suffix_for_user,
    postgres_user,
)
from dataworkspace.apps.explorer import app_settings


logger = logging.getLogger('app')
EXPLORER_PARAM_TOKEN = "$$"


def _format_field(field):
    return field.get_attname_column()[1], field.get_internal_type()


def param(name):
    return "%s%s%s" % (EXPLORER_PARAM_TOKEN, name, EXPLORER_PARAM_TOKEN)


def swap_params(sql, params):
    p = params.items() if params else {}
    for k, v in p:
        regex = re.compile(r"\$\$%s(?:\:([^\$]+))?\$\$" % str(k).lower(), re.I)
        sql = regex.sub(text_type(v), sql)
    return sql


def extract_params(text):
    regex = re.compile(r"\$\$([a-z0-9_]+)(?:\:([^\$]+))?\$\$")
    params = re.findall(regex, text.lower())
    return {p[0]: p[1] if len(p) > 1 else '' for p in params}


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


def shared_dict_update(target, source):
    for k_d1 in target:
        if k_d1 in source:
            target[k_d1] = source[k_d1]
    return target


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


def get_params_for_url(query):  # pylint: disable=inconsistent-return-statements
    if query.params:
        return '|'.join(['%s:%s' % (p, v) for p, v in query.params.items()])


def url_get_rows(request):
    return int(request.POST.get("query-rows", app_settings.EXPLORER_DEFAULT_ROWS))


def url_get_page(request):
    return int(request.POST.get("query-page", 1))


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

    cache_key = user_cached_credentials_key(user)
    user_credentials = cache.get(cache_key, None)

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
def user_explorer_connection(user, alias=None):
    connection_settings = get_user_explorer_connection_settings(user, alias)

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
