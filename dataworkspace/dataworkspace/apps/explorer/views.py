from urllib.parse import urlencode

from psycopg2 import DatabaseError

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.db.models import Count
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
from waffle import flag_is_active

from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.apps.explorer.exporters import get_exporter_class
from dataworkspace.apps.explorer.forms import QueryForm
from dataworkspace.apps.explorer.models import Query, QueryLog, PlaygroundSQL
from dataworkspace.apps.explorer.schema import schema_info
from dataworkspace.apps.explorer.tasks import execute_query
from dataworkspace.apps.explorer.utils import (
    fetch_query_results,
    get_total_pages,
    QueryException,
    url_get_log_id,
    url_get_page,
    url_get_params,
    url_get_query_id,
    url_get_rows,
    url_get_show,
)
from dataworkspace.utils import DATA_EXPLORER_ASYNC_QUERIES_FLAG


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


class DownloadFromQuerylogView(View):
    def get(self, request, querylog_id):
        querylog = get_object_or_404(
            QueryLog, pk=querylog_id, run_by_user=self.request.user
        )

        query = Query(
            sql=querylog.sql,
            connection=querylog.connection,
            title=querylog.query.title
            if querylog.query
            else f'Playground - {querylog.sql[:32]}',
        )
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
            if len(ret) == settings.EXPLORER_RECENT_QUERY_COUNT:
                break

            if ql.query_id not in tracker:
                ret.append(ql)
                tracker.append(ql.query_id)
        return ret

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_list'] = self.object_list
        context['recent_queries'] = self.recently_viewed()
        return context

    def get_queryset(self):
        qs = (
            Query.objects.filter(created_by_user=self.request.user)
            .order_by('-created_at')
            .all()
        )
        return qs.annotate(run_count=Count('querylog'))

    model = Query
    paginate_by = 15


class ListQueryLogView(ListView):
    def get_queryset(self):
        kwargs = {'sql__isnull': False, 'run_by_user': self.request.user}
        if url_get_query_id(self.request):
            kwargs['query_id'] = url_get_query_id(self.request)
        return QueryLog.objects.filter(**kwargs).order_by('-run_at').all()

    context_object_name = "recent_logs"
    model = QueryLog
    paginate_by = 15


class CreateQueryView(CreateView):
    def form_valid(self, form):
        form.instance.created_by_user = self.request.user
        return super().form_valid(form)

    def get_initial(self):
        data = super().get_initial()

        play_sql = get_playground_sql_from_request(self.request)
        if play_sql:
            data['sql'] = play_sql.sql

        return data

    def get(self, request, *args, **kwargs):
        extra_context = {}

        play_sql = get_playground_sql_from_request(request)
        extra_context['disable_sql'] = True
        extra_context['backlink'] = (
            reverse("explorer:index") + f"?play_id={play_sql.id}"
        )

        extra_context['form_action'] = request.get_full_path()

        response = super().get(request, *args, **kwargs)
        response.context_data.update(extra_context)

        return response

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        play_sql = get_playground_sql_from_request(request)

        if action == 'edit':
            if not play_sql:
                play_sql = PlaygroundSQL(
                    sql=request.POST.get("sql", ""), created_by_user=request.user
                )
                play_sql.save()

            redirect_url = reverse('explorer:index')

            return redirect(redirect_url + f"?play_id={play_sql.id}")

        if action == 'save':
            ret = super().post(request)
            if self.get_form().is_valid():
                query, form = QueryView.get_instance_and_form(
                    request, self.object.id, play_sql=play_sql
                )

                if form.is_valid():
                    form.save()

                vm = query_viewmodel(
                    request,
                    query,
                    form=form,
                    run_query=False,
                    rows=url_get_rows(request),
                    page=url_get_page(request),
                    message=None,
                )

                if vm['form'].errors:
                    self.object.delete()
                    del vm['query']
                    vm['form_action'] = request.get_full_path()

                    return render(request, self.template_name, vm)

                messages.success(request, "Your query has been saved.")
                log_event(
                    request.user,
                    EventLog.TYPE_DATA_EXPLORER_SAVED_QUERY,
                    related_object=query,
                    extra={"sql": query.sql},
                )
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
        tables_columns = ['.'.join(schema_table) for schema_table, _ in schema]
        return schema, tables_columns

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

        initial_data = {"sql": request.GET.get('sql')}

        play_sql = get_playground_sql_from_request(request)
        if play_sql:
            initial_data['sql'] = play_sql.sql

        schema, tables_columns = self._schema_info(request)
        return render(
            self.request,
            'explorer/home.html',
            {
                'title': 'Playground',
                'form': QueryForm(initial=initial_data),
                'form_action': self.get_form_action(request),
                'schema': schema,
                'schema_tables': tables_columns,
            },
        )

    def post(self, request):
        sql = request.POST.get('sql')
        action = request.POST.get('action', '')
        existing_query_id = url_get_query_id(request)

        if existing_query_id:
            query = get_object_or_404(
                Query, pk=existing_query_id, created_by_user=self.request.user
            )
        else:
            query = Query(
                sql=sql, title="Playground", connection=request.POST.get('connection')
            )

        if action == 'save':
            play_sql, _ = PlaygroundSQL.objects.get_or_create(
                sql=sql, created_by_user=request.user
            )
            play_sql.save()

            if existing_query_id:
                redirect_url = reverse(
                    'explorer:query_detail', kwargs={"query_id": existing_query_id},
                )
            else:
                redirect_url = reverse('explorer:query_create')

            query_params = (("play_id", play_sql.id),)
            return redirect(redirect_url + f"?{urlencode(query_params)}")

        elif action in {'run', 'fetch-page'}:
            query.params = url_get_params(request)
            response = self.render_with_sql(request, query, run_query=True)

            return response

        else:
            return HttpResponse(f"Unknown form action: {action}", 400)

    def get_form_action(self, request):
        form_action_params = urlencode(
            tuple(
                (k, v)
                for k, v in request.GET.items()
                if k not in {'sql', 'querylog_id', 'play_id'}
            )
        )

        form_action = request.path
        if form_action_params:
            form_action += "?" + form_action_params

        return form_action

    def render_with_sql(self, request, query, run_query=True):
        rows = url_get_rows(request)
        page = url_get_page(request)
        form = QueryForm(
            request.POST if request.method == 'POST' else None, instance=query
        )

        # If there's custom SQL in URL params, override anything from the query. This may happen if someone is editing
        # a query, goes to save it, then clicks the backlink. We need to preserve their edited SQL rather than just
        # loading the old saved query SQL, and we do that by passing the new SQL through as a query param.
        if request.method == 'GET':
            if request.GET.get('sql'):
                form.initial['sql'] = request.GET.get('sql')
            else:
                play_sql = get_playground_sql_from_request(request)
                if play_sql:
                    form.initial['sql'] = play_sql.sql

        context = query_viewmodel(
            request,
            query,
            title="Home",
            run_query=run_query and form.is_valid(),
            rows=rows,
            page=page,
            form=form,
        )
        schema, tables_columns = self._schema_info(request)
        context['schema'] = schema
        context['schema_tables'] = tables_columns
        context['form_action'] = self.get_form_action(request)
        return render(self.request, 'explorer/home.html', context)


class QueryView(View):
    def get(self, request, query_id):
        play_sql = get_playground_sql_from_request(request)
        query, form = QueryView.get_instance_and_form(
            request, query_id, play_sql=play_sql
        )
        query.save()  # updates the modified date

        context = {
            'form': form,
            'form_action': request.get_full_path(),
            'query': query,
            'backlink': self.get_edit_sql_url(request, query) if play_sql else None,
        }
        return render(self.request, 'explorer/query.html', context)

    def post(self, request, query_id):
        action = request.POST.get("action", "")
        play_sql = get_playground_sql_from_request(request)

        if action == 'save':
            show = url_get_show(request)
            query, form = QueryView.get_instance_and_form(
                request, query_id, play_sql=play_sql
            )
            success = form.is_valid() and form.save()
            vm = query_viewmodel(
                request,
                query,
                form=form,
                run_query=show,
                rows=url_get_rows(request),
                page=url_get_page(request),
                message=None,
            )
            if success:
                messages.success(request, "Your query has been updated.")
                log_event(
                    request.user,
                    EventLog.TYPE_DATA_EXPLORER_SAVED_QUERY,
                    related_object=query,
                    extra={"sql": query.sql},
                )
                return redirect(
                    reverse('explorer:query_detail', kwargs={"query_id": query.id})
                )

            vm['form_action'] = request.get_full_path()
            return render(self.request, 'explorer/query.html', vm)

        elif action == 'edit':
            query, _ = QueryView.get_instance_and_form(
                request, query_id, play_sql=play_sql
            )

            return HttpResponseRedirect(self.get_edit_sql_url(request, query))

        else:
            return HttpResponseBadRequest(f"Unknown form action: {action}")

    @staticmethod
    def get_edit_sql_url(request, query):
        query_params = (('query_id', query.id),)

        play_sql = get_playground_sql_from_request(request)
        if play_sql:
            query_params = query_params + (('play_id', play_sql.id),)

        return reverse('explorer:index') + f"?{urlencode(query_params)}"

    @staticmethod
    def get_instance_and_form(request, query_id, play_sql=None):
        query = get_object_or_404(Query, pk=query_id, created_by_user=request.user)
        query.params = url_get_params(request)
        form = QueryForm(
            request.POST if len(request.POST) > 0 else None, instance=query
        )

        if play_sql:
            form.initial['sql'] = play_sql.sql

        return query, form


def get_playground_sql_from_request(request):
    if request.GET.get("play_id"):
        try:
            return PlaygroundSQL.objects.get(
                id=request.GET.get("play_id"), created_by_user=request.user
            )
        except PlaygroundSQL.DoesNotExist:
            pass

    return None


def query_viewmodel(
    request,
    query,
    title=None,
    form=None,
    message=None,
    run_query=True,
    rows=settings.EXPLORER_DEFAULT_ROWS,
    timeout=settings.EXPLORER_QUERY_TIMEOUT_MS,
    page=1,
    method="POST",
    log=True,
):
    error = None
    if run_query:
        try:
            if flag_is_active(request, DATA_EXPLORER_ASYNC_QUERIES_FLAG):
                query_log_id = execute_query.delay(
                    query.final_sql(),
                    query.connection,
                    query.id,
                    request.user.id,
                    page,
                    rows,
                    timeout,
                ).get()
            else:
                query_log_id = execute_query(
                    query.final_sql(),
                    query.connection,
                    query.id,
                    request.user.id,
                    page,
                    rows,
                    timeout,
                )

            headers, data, query_log = fetch_query_results(query_log_id)
        except QueryException as e:
            error = str(e)
    if error and method == "POST":
        form.add_error('sql', error)
        message = "Query error"
    has_valid_results = not error and run_query
    ret = {
        'params': query.available_params(),
        'title': title,
        'query': query,
        'form': form,
        'message': message,
        'rows': rows,
        'page': page,
        'data': data if has_valid_results else None,
        'headers': headers if has_valid_results else None,
        'total_rows': query_log.rows if has_valid_results else None,
        'duration': query_log.duration if has_valid_results else None,
        'unsafe_rendering': settings.EXPLORER_UNSAFE_RENDERING,
        'query_log': query_log if has_valid_results else None,
    }
    ret['total_pages'] = get_total_pages(ret['total_rows'], rows)

    return ret
