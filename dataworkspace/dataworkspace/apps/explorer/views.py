import re

from collections import Counter
from urllib.parse import urlencode

from psycopg2 import DatabaseError
import six

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.forms.models import model_to_dict
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseBadRequest,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView
from django.views.generic.base import View
from django.views.generic.edit import CreateView, DeleteView

from dataworkspace.apps.explorer import app_settings
from dataworkspace.apps.explorer.exporters import get_exporter_class
from dataworkspace.apps.explorer.forms import QueryForm
from dataworkspace.apps.explorer.models import Query, QueryLog
from dataworkspace.apps.explorer.schema import schema_info
from dataworkspace.apps.explorer.utils import (
    get_total_pages,
    url_get_log_id,
    url_get_page,
    url_get_params,
    url_get_query_id,
    url_get_rows,
    url_get_show,
)


class SafeLoginView(LoginView):
    template_name = 'admin/login.html'


def _export(request, query, download=True):
    format_ = request.GET.get('format', 'csv')
    exporter_class = get_exporter_class(format_)
    query.params = url_get_params(request)
    delim = request.GET.get('delim')
    exporter = exporter_class(query=query, user=request.user)
    try:
        output = exporter.get_output(delim=delim)
    except DatabaseError as e:
        msg = "Error executing query %s: %s" % (query.title, e)
        return HttpResponse(msg, status=500)
    response = HttpResponse(output, content_type=exporter.content_type)
    if download:
        response['Content-Disposition'] = 'attachment; filename="%s"' % (
            exporter.get_filename()
        )
    return response


class DownloadQueryView(View):
    def get(self, request, query_id, *args, **kwargs):
        query = get_object_or_404(Query, pk=query_id)
        resp = _export(request, query)
        if (
            isinstance(resp, HttpResponse)
            and resp.status_code == 500
            and "Error executing query" in resp.content.decode(resp.charset)
        ):
            return HttpResponseRedirect(
                reverse_lazy('explorer:query_detail', kwargs={'query_id': query_id})
            )
        return resp


class DownloadFromSqlView(View):
    def get(self, request, *args, **kwargs):
        sql = request.GET.get('sql')
        connection = request.GET.get('connection')
        query = Query(sql=sql, connection=connection, title='')
        ql = query.log(request.user)
        query.title = 'Playground - %s' % ql.id
        return _export(request, query)

    def post(self, request, *args, **kwargs):
        sql = request.POST.get('sql')
        connection = request.POST.get('connection')
        query = Query(sql=sql, connection=connection, title='')
        ql = query.log(request.user)
        query.title = 'Playground - %s' % ql.id
        return _export(request, query)


class ListQueryView(ListView):
    def recently_viewed(self):
        qll = (
            QueryLog.objects.filter(
                run_by_user=self.request.user,
                query_id__isnull=False,
                query__created_by_user=self.request.user,
            )
            .order_by('-run_at')
            .select_related('query')
        )
        ret = []
        tracker = []
        for ql in qll:
            if len(ret) == app_settings.EXPLORER_RECENT_QUERY_COUNT:
                break

            if ql.query_id not in tracker:
                ret.append(ql)
                tracker.append(ql.query_id)
        return ret

    def get_context_data(self, **kwargs):
        context = super(ListQueryView, self).get_context_data(**kwargs)
        context['object_list'] = self._build_queries_and_headers()
        context['recent_queries'] = self.recently_viewed()
        return context

    def get_queryset(self):
        qs = Query.objects.filter(created_by_user=self.request.user).all()
        return qs.annotate(run_count=Count('querylog'))

    def _build_queries_and_headers(self):
        """
        Build a list of query information and headers (pseudo-folders)
        for consumption by the template.

        Strategy: Look for queries with titles of the form "something - else"
        (eg. with a ' - ' in the middle)
        and split on the ' - ', treating the left side as a "header" (or folder). Interleave the
        headers into the ListView's object_list as appropriate. Ignore headers that only have one
        child. The front end uses bootstrap's JS Collapse plugin, which necessitates generating CSS
        classes to map the header onto the child rows, hence the collapse_target variable.

        To make the return object homogeneous, convert the object_list models into dictionaries for
        interleaving with the header "objects". This necessitates special handling of 'created_at'
        and 'created_by_user' because model_to_dict doesn't include non-editable fields (created_at)
        and will give the int representation of the user instead of the string representation.

        :return: A list of model dictionaries representing all the query objects,
        interleaved with header dictionaries.
        """

        dict_list = []
        rendered_headers = []
        pattern = re.compile(r'[\W_]+')

        headers = Counter([q.title.split(' - ')[0] for q in self.object_list])

        for q in self.object_list:
            model_dict = model_to_dict(q)
            header = q.title.split(' - ')[0]
            collapse_target = pattern.sub('', header)

            if headers[header] > 1 and header not in rendered_headers:
                dict_list.append(
                    {
                        'title': header,
                        'is_header': True,
                        'is_in_category': False,
                        'collapse_target': collapse_target,
                        'count': headers[header],
                    }
                )
                rendered_headers.append(header)

            model_dict.update(
                {
                    'is_in_category': headers[header] > 1,
                    'collapse_target': collapse_target,
                    'created_at': q.created_at,
                    'is_header': False,
                    'run_count': q.run_count,
                    'created_by_user': six.text_type(q.created_by_user.email)
                    if q.created_by_user
                    else None,
                }
            )

            dict_list.append(model_dict)
        return dict_list

    model = Query


class ListQueryLogView(ListView):
    def get_queryset(self):
        kwargs = {'sql__isnull': False, 'run_by_user': self.request.user}
        if url_get_query_id(self.request):
            kwargs['query_id'] = url_get_query_id(self.request)
        return QueryLog.objects.filter(**kwargs).all()

    context_object_name = "recent_logs"
    model = QueryLog
    paginate_by = 20


class CreateQueryView(CreateView):
    def form_valid(self, form):
        form.instance.created_by_user = self.request.user
        return super().form_valid(form)

    def get_initial(self):
        data = super().get_initial()

        sql = self.request.GET.get("sql")
        if sql:
            data['sql'] = sql

        return data

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        sql = self.request.GET.get("sql")
        if sql:
            response.context_data['disable_sql'] = True

        query_params = (('sql', request.GET.get('sql')),)
        response.context_data['backlink'] = (
            reverse("explorer:index") + f"?{urlencode(query_params)}"
        )

        return response

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')

        if action == 'save':
            ret = super().post(request)
            if self.get_form().is_valid():
                show = url_get_show(request)
                query, form = QueryView.get_instance_and_form(request, self.object.id)
                success = form.is_valid() and form.save()
                vm = query_viewmodel(
                    request.user,
                    query,
                    form=form,
                    run_query=show,
                    rows=url_get_rows(request),
                    page=url_get_page(request),
                    message="Query created." if success else None,
                    log=False,
                )
                if vm['form'].errors:
                    self.object.delete()
                    del vm['query']

                    return render(request, self.template_name, vm)

                return HttpResponseRedirect(
                    reverse_lazy(
                        'explorer:query_detail', kwargs={'query_id': self.object.id}
                    )
                )

            return ret

        elif action == 'edit':
            query_params = (('sql', request.POST.get('sql')),)
            return HttpResponseRedirect(
                reverse('explorer:index') + f"?{urlencode(query_params)}"
            )

        else:
            return HttpResponse(f"Unknown form action: {action}", 400)

    form_class = QueryForm
    template_name = 'explorer/query.html'


class DeleteQueryView(DeleteView):
    model = Query
    success_url = reverse_lazy("explorer:list_queries")

    def get_queryset(self):
        return Query.objects.filter(created_by_user=self.request.user).all()


class PlayQueryView(View):
    def _schema_info(self, request):
        schema = schema_info(
            user=request.user, connection_alias=settings.EXPLORER_DEFAULT_CONNECTION
        )
        # used for autocomplete
        return schema, ['.'.join(schema_table) for schema_table, _ in schema]

    def get(self, request):
        if url_get_query_id(request):
            query = get_object_or_404(
                Query, pk=url_get_query_id(request), created_by_user=self.request.user
            )
            return self.render_with_sql(request, query, run_query=False)

        if url_get_log_id(request):
            log = get_object_or_404(
                QueryLog, pk=url_get_log_id(request), run_by_user=self.request.user
            )
            query = Query(sql=log.sql, title="Playground", connection=log.connection)
            return self.render_with_sql(request, query)

        schema, tables_columns = self._schema_info(request)

        return render(
            self.request,
            'explorer/home.html',
            {
                'title': 'Playground',
                'form': QueryForm(initial={"sql": request.GET.get('sql')}),
                'form_action': self.get_form_action(request),
                'schema': schema,
                'schema_tables': tables_columns,
            },
        )

    def post(self, request):
        sql = request.POST.get('sql')
        action = request.POST.get('action', '')
        existing_query_id = url_get_query_id(request)

        if action.startswith("download"):
            download_format = action.split('-')[1]
            query_params = (('sql', sql), ('format', download_format))
            return HttpResponseRedirect(
                reverse('explorer:download_sql') + f"?{urlencode(query_params)}"
            )

        if existing_query_id:
            query = get_object_or_404(
                Query, pk=existing_query_id, created_by_user=self.request.user
            )
        else:
            query = Query(
                sql=sql, title="Playground", connection=request.POST.get('connection')
            )

        if action == 'save':
            if existing_query_id:
                query_params = (("sql", sql), ('from', 'play'))

                return redirect(
                    reverse(
                        'explorer:query_detail', kwargs={"query_id": existing_query_id}
                    )
                    + f"?{urlencode(query_params)}"
                )

            query_params = (('sql', sql),)
            return redirect(
                reverse('explorer:query_create') + f"?{urlencode(query_params)}"
            )

        elif action in {'run', 'fetch-page'}:
            query.params = url_get_params(request)
            response = self.render_with_sql(request, query, run_query=True, log=True)

            return response

        else:
            return HttpResponse(f"Unknown form action: {action}", 400)

    def get_form_action(self, request):
        form_action_params = urlencode(
            tuple(
                (k, v)
                for k, v in request.GET.items()
                if k not in {'sql', 'querylog_id'}
            )
        )

        form_action = request.path
        if form_action_params:
            form_action += "?" + form_action_params

        return form_action

    def render_with_sql(self, request, query, run_query=True, log=False):
        rows = url_get_rows(request)
        page = url_get_page(request)
        form = QueryForm(
            request.POST if request.method == 'POST' else None, instance=query
        )

        # If there's custom SQL in URL params, override anything from the query. This may happen if someone is editing
        # a query, goes to save it, then clicks the backlink. We need to preserve their edited SQL rather than just
        # loading the old saved query SQL, and we do that by passing the new SQL through as a query param.
        if request.method == 'GET' and request.GET.get('sql'):
            form.initial['sql'] = request.GET.get('sql')

        context = query_viewmodel(
            request.user,
            query,
            title="Home",
            run_query=run_query and form.is_valid(),
            rows=rows,
            page=page,
            form=form,
            log=log,
        )

        schema, tables_columns = self._schema_info(request)

        context['schema'] = schema
        context['schema_tables'] = tables_columns
        context['form_action'] = self.get_form_action(request)
        return render(self.request, 'explorer/home.html', context)


class QueryView(View):
    def get(self, request, query_id):
        query, form = QueryView.get_instance_and_form(request, query_id)
        query.save()  # updates the modified date

        # Overwrite SQL form field from GET query parameter (sent when saving an existing query from the playground).
        sql = request.GET.get("sql")
        if sql:
            form.initial['sql'] = sql

        context = {'form': form, 'query': query}
        if request.GET.get("from") == "play":
            query_params = (('sql', form.initial['sql']), ('query_id', query.id))
            context['backlink'] = (
                reverse("explorer:index") + f"?{urlencode(query_params)}"
            )

        return render(self.request, 'explorer/query.html', context)

    def post(self, request, query_id):
        action = request.POST.get("action", "")

        if action == 'save':
            show = url_get_show(request)
            query, form = QueryView.get_instance_and_form(request, query_id)
            success = form.is_valid() and form.save()
            vm = query_viewmodel(
                request.user,
                query,
                form=form,
                run_query=show,
                rows=url_get_rows(request),
                page=url_get_page(request),
                message="Query saved." if success else None,
            )
            return render(self.request, 'explorer/query.html', vm)

        elif action == 'edit':
            query, form = QueryView.get_instance_and_form(request, query_id)
            query_params = (('query_id', query.id), ('sql', request.POST.get('sql')))
            return HttpResponseRedirect(
                reverse('explorer:index') + f"?{urlencode(query_params)}"
            )

        else:
            return HttpResponseBadRequest(f"Unknown form action: {action}")

    @staticmethod
    def get_instance_and_form(request, query_id):
        query = get_object_or_404(Query, pk=query_id, created_by_user=request.user)
        query.params = url_get_params(request)
        form = QueryForm(
            request.POST if len(request.POST) > 0 else None, instance=query
        )
        return query, form


def query_viewmodel(
    user,
    query,
    title=None,
    form=None,
    message=None,
    run_query=True,
    rows=app_settings.EXPLORER_DEFAULT_ROWS,
    timeout=app_settings.EXPLORER_QUERY_TIMEOUT_MS,
    page=1,
    method="POST",
    log=True,
):
    res = None
    ql = None
    error = None
    if run_query:
        try:
            if log:
                res, ql = query.execute_with_logging(user, page, rows, timeout)
            else:
                res = query.execute(user, page, rows, timeout)
        except DatabaseError as e:
            error = str(e)
    if error and method == "POST":
        form.add_error('sql', error)
        message = "Query error"
    has_valid_results = not error and res and run_query
    ret = {
        'params': query.available_params(),
        'title': title,
        'query': query,
        'form': form,
        'message': message,
        'rows': rows,
        'page': page,
        'data': res.data if has_valid_results else None,
        'headers': res.headers if has_valid_results else None,
        'total_rows': res.row_count if has_valid_results else None,
        'duration': res.duration if has_valid_results else None,
        'has_stats': len([h for h in res.headers if h.summary])
        if has_valid_results
        else False,
        'ql_id': ql.id if ql else None,
        'unsafe_rendering': app_settings.UNSAFE_RENDERING,
    }
    ret['total_pages'] = get_total_pages(ret['total_rows'], rows)

    return ret
