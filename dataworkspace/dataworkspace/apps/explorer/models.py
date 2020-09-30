from __future__ import unicode_literals

import logging
import uuid
from time import time

import six
from dynamic_models.models import AbstractFieldSchema, AbstractModelSchema  # noqa: I202
from django.conf import settings
from django.db import DatabaseError, models

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse

from dataworkspace.apps.explorer.utils import (
    extract_params,
    get_params_for_url,
    user_explorer_connection,
    shared_dict_update,
    swap_params,
    get_user_explorer_connection_settings,
)

logger = logging.getLogger(__name__)


@six.python_2_unicode_compatible
class Query(models.Model):
    title = models.CharField(max_length=255)
    sql = models.TextField()
    description = models.TextField(null=True, blank=True)
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_run_date = models.DateTimeField(auto_now=True)
    connection = models.CharField(
        blank=True,
        null=True,
        max_length=128,
        help_text="Name of DB connection (as specified in settings) to use for this query."
        " Will use EXPLORER_DEFAULT_CONNECTION if left blank",
    )

    def __init__(self, *args, **kwargs):
        self.params = kwargs.get('params')
        kwargs.pop('params', None)
        super(Query, self).__init__(*args, **kwargs)

    class Meta:
        ordering = ['title']
        verbose_name_plural = 'Queries'

    def __str__(self):
        return six.text_type(self.title)

    def get_run_count(self):
        return self.querylog_set.count()

    def avg_duration(self):
        return self.querylog_set.aggregate(models.Avg('duration'))['duration__avg']

    def final_sql(self):
        return swap_params(self.sql, self.available_params())

    def execute_with_logging(self, executing_user, page, limit, timeout):
        ql = self.log(executing_user)
        ret = self.execute(executing_user, page, limit, timeout)
        ql.duration = ret.duration
        ql.save()
        return ret, ql

    def execute(self, executing_user, page, limit, timeout):
        user_connection_settings = get_user_explorer_connection_settings(
            executing_user, self.connection
        )
        with user_explorer_connection(user_connection_settings) as conn:
            result = QueryResult(
                self.final_sql(), conn, page, limit=limit, timeout=timeout,
            )
            result.process()
            return result

    def available_params(self):
        """
        Merge parameter values into a dictionary of available parameters

        :param param_values: A dictionary of Query param values.
        :return: A merged dictionary of parameter names and values.
         Values of non-existent parameters are removed.
        """

        p = extract_params(self.sql)
        if self.params:
            shared_dict_update(p, self.params)
        return p

    def get_absolute_url(self):
        return reverse("explorer:query_detail", kwargs={'query_id': self.id})

    @property
    def params_for_url(self):
        return get_params_for_url(self)

    def log(self, user=None):
        if user:
            # In Django<1.10, is_anonymous was a method.
            try:
                is_anonymous = user.is_anonymous()
            except TypeError:
                is_anonymous = user.is_anonymous
            if is_anonymous:
                user = None
        ql = QueryLog(
            sql=self.final_sql(),
            query_id=self.id,
            run_by_user=user,
            connection=self.connection,
        )
        ql.save()
        return ql


class QueryLog(models.Model):

    sql = models.TextField(null=True, blank=True)
    query = models.ForeignKey(Query, null=True, blank=True, on_delete=models.SET_NULL)
    run_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    run_at = models.DateTimeField(auto_now_add=True)
    duration = models.FloatField(blank=True, null=True)  # milliseconds
    connection = models.CharField(blank=True, null=True, max_length=128)

    @property
    def is_playground(self):
        return self.query_id is None

    class Meta:
        ordering = ['-run_at']


class QueryResult:
    def __init__(self, sql, connection, page, limit, timeout):
        self.sql = sql
        self.connection = connection
        self.limit = limit
        self.timeout = timeout
        self._row_count = None
        self._data = []
        self._headers = []
        self._summary = {}
        self._description = None
        self.duration = None
        self.page = page
        self.execute_query()

    def execute_query(self):
        with self.connection.cursor() as cursor:
            sql_query = SQLQuery(cursor, self.sql, self.limit, self.page, self.timeout)
            self._data = sql_query.get_results()
            self._description = sql_query.description
            self._headers = self._get_headers()
            self._row_count = sql_query.count
            self.duration = sql_query.duration

    @property
    def data(self):
        return self._data or []

    @property
    def row_count(self):
        if self._row_count is None:
            return len(self.data)
        return self._row_count

    @property
    def headers(self):
        return self._headers or []

    @property
    def header_strings(self):
        return [str(h) for h in self.headers]

    def _get_headers(self):
        return (
            [ColumnHeader(d[0]) for d in self._description]
            if self._description
            else [ColumnHeader('--')]
        )

    def _get_numerics(self):
        if self.data:
            d = self.data[0]
            return [
                ix
                for ix, _ in enumerate(self._description)
                if not isinstance(d[ix], six.string_types)
                and six.text_type(d[ix]).isnumeric()
            ]
        return []

    def column(self, ix):
        return [r[ix] for r in self.data]

    def process(self):
        start_time = time()
        self.process_columns()
        logger.info(
            "Explorer Query Processing took %sms.", ((time() - start_time) * 1000)
        )

    def process_columns(self):
        for ix in self._get_numerics():
            self.headers[ix].add_summary(self.column(ix))


class SQLQuery:
    def __init__(self, cursor, sql, limit, page, timeout):
        self.cursor = cursor
        self.sql = sql
        self.limit = limit
        self.page = page
        self.timeout = timeout
        self.duration = 0
        self._cursor_name = None
        self._count = 0
        self._description = None

    @property
    def count(self):
        if not self._count:
            # trim whitespace and semicolons from the end of the query string
            sql = self.sql.rstrip().rstrip(';')
            self.cursor.execute(f'select count(*) from ({sql}) t')
            self._count = self.cursor.fetchone()[0]
        return self._count

    def execute(self):
        start_time = time()
        try:
            self._execute()
        except DatabaseError as e:
            raise e
        self.duration = (time() - start_time) * 1000

    def _execute(self):
        self.cursor.execute(f'SET statement_timeout = {self.timeout}')
        self.cursor.execute(
            f'DECLARE {self.cursor_name} CURSOR WITH HOLD FOR {self.sql}'
        )
        if self.page and self.page > 1:
            offset = (self.page - 1) * self.limit
            self.cursor.execute(f'MOVE {offset} FROM {self.cursor_name}')
        self.cursor.execute(f'FETCH {self.limit} FROM {self.cursor_name}')

    def get_results(self):
        self.execute()
        self._description = self.cursor.description or []
        results = [list(r) for r in self.cursor]
        self.cursor.execute(f'CLOSE {self.cursor_name}')
        return results

    @property
    def cursor_name(self):
        if not self._cursor_name:
            self._cursor_name = 'cur_%s' % str(uuid.uuid4()).replace('-', '')[:10]
        return self._cursor_name

    @property
    def description(self):
        return self._description


@six.python_2_unicode_compatible
class ColumnHeader:
    def __init__(self, title):
        self.title = title.strip()
        self.summary = None

    def add_summary(self, column):
        self.summary = ColumnSummary(self, column)

    def __str__(self):
        return self.title


@six.python_2_unicode_compatible
class ColumnStat:
    def __init__(self, label, statfn, precision=2, handles_null=False):
        self.label = label
        self.statfn = statfn
        self.precision = precision
        self.handles_null = handles_null

    def __call__(self, coldata):
        self.value = (  # pylint: disable=attribute-defined-outside-init
            round(float(self.statfn(coldata)), self.precision) if coldata else 0
        )

    def __str__(self):
        return self.label


@six.python_2_unicode_compatible
class ColumnSummary:
    def __init__(self, header, col):
        self._header = header
        self._stats = [
            ColumnStat("Sum", sum),
            ColumnStat("Avg", lambda x: float(sum(x)) / float(len(x))),
            ColumnStat("Min", min),
            ColumnStat("Max", max),
            ColumnStat(
                "NUL",
                lambda x: int(sum(map(lambda y: 1 if y is None else 0, x))),
                0,
                True,
            ),
        ]
        without_nulls = list(map(lambda x: 0 if x is None else x, col))

        for stat in self._stats:
            stat(  # pylint: disable=expression-not-assigned
                col
            ) if stat.handles_null else stat(without_nulls)

    @property
    def stats(self):
        return {c.label: c.value for c in self._stats}

    def __str__(self):
        return str(self._header)


class ModelSchema(AbstractModelSchema):
    name = models.CharField(max_length=256, unique=True)


class FieldSchema(AbstractFieldSchema):
    name = models.CharField(max_length=256, unique=True)
