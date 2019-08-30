import logging

from django.http import (HttpResponse, HttpResponseRedirect, HttpResponseForbidden, HttpResponseNotAllowed,
                         HttpResponseNotFound)
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.core.forms import SupportForm
from dataworkspace.apps.core.utils import can_access_schema_table, table_exists, \
    table_data
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.zendesk import create_support_request

logger = logging.getLogger('app')


def public_error_404_html_view(request, exception=None):
    return render(request, 'error_404.html', status=404)


def public_error_403_html_view(request, exception=None):
    return render(request, 'error_403.html', status=403)


def public_error_500_html_view(request):
    message = request.GET.get('message', None)
    return render(request, 'error_500.html', {'message': message}, status=500)


def public_error_400_html_view(request, exception=None):
    return render(request, 'error_400.html', {'message': str(exception)}, status=400)


def healthcheck_view(_):
    return HttpResponse('OK')


class SupportView(FormView):
    form_class = SupportForm
    template_name = 'core/support.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['ticket_id'] = self.kwargs.get('ticket_id')
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'email': self.request.user.email,
        }
        return kwargs

    def form_valid(self, form):
        cleaned = form.cleaned_data
        ticket_id = create_support_request(
            self.request.user,
            cleaned['email'],
            cleaned['message'],
            attachments=[cleaned[x] for x in [
                'attachment1', 'attachment2', 'attachment3'
            ] if cleaned[x] is not None]
        )
        return HttpResponseRedirect(
            reverse('support-success', kwargs={'ticket_id': ticket_id})
        )


def table_data_view(request, database, schema, table):
    logger.info('table_data_view attempt: %s %s %s %s',
                request.user.email, database, schema, table)

    log_event(
        request.user,
        EventLog.TYPE_DATASET_TABLE_DATA_DOWNLOAD,
        extra={
            'path': request.get_full_path(),
            'database': database,
            'schema': schema,
            'table': table,
        }
    )

    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseForbidden() if not can_access_schema_table(request.user, database, schema, table) else \
        HttpResponseNotFound() if not table_exists(database, schema, table) else \
        table_data(request.user.email, database, schema, table)

    return response
