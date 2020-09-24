import re


import sqlparse
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from six import text_type

from dataworkspace.apps.explorer import app_settings

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


def get_valid_connection(alias=None):
    from dataworkspace.apps.explorer.connections import (  # pylint: disable=import-outside-toplevel
        connections,
    )

    if not alias:
        return connections[settings.EXPLORER_DEFAULT_CONNECTION]

    if alias not in connections:
        raise InvalidExplorerConnectionException(
            'Attempted to access connection %s, but that is not a registered Explorer connection.'
            % alias
        )
    return connections[alias]


def get_total_pages(total_rows, page_size):
    if not total_rows or not page_size:
        return 1
    remainder = total_rows % page_size
    if remainder:
        remainder = 1
    return int(total_rows / page_size) + remainder
