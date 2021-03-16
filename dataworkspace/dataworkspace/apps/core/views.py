import logging

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView

from dataworkspace.apps.core.forms import SupportForm, UserSatisfactionSurveyForm
from dataworkspace.apps.core.models import UserSatisfactionSurvey
from dataworkspace.apps.core.utils import (
    can_access_schema_table,
    table_data,
    table_exists,
    view_exists,
)
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


def healthcheck_view(_):
    return HttpResponse('OK')


def about_page_view(request):
    return render(request, 'about.html', {}, status=200)


class SupportView(FormView):
    form_class = SupportForm
    template_name = 'core/support.html'

    ZENDESK_TAGS = {"data-request": "data_request"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['ticket_id'] = self.kwargs.get('ticket_id')
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {'email': self.request.user.email}
        return kwargs

    def form_valid(self, form):
        cleaned = form.cleaned_data

        tag = self.ZENDESK_TAGS.get(self.request.GET.get('tag'))
        ticket_id = create_support_request(
            self.request.user, cleaned['email'], cleaned['message'], tag=tag
        )
        return HttpResponseRedirect(
            reverse('support-success', kwargs={'ticket_id': ticket_id})
        )


class UserSatisfactionSurveyView(FormView):
    form_class = UserSatisfactionSurveyForm
    template_name = 'core/user-satisfaction-survey.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['referer'] = self.request.META.get('HTTP_REFERER')
        return ctx

    def form_valid(self, form):
        cleaned = form.cleaned_data
        UserSatisfactionSurvey.objects.create(
            how_satisfied=cleaned['how_satisfied'],
            trying_to_do=','.join(cleaned['trying_to_do']),
            improve_service=cleaned['improve_service'],
        )

        return HttpResponseRedirect(f'{reverse("feedback")}?success=1')


def table_data_view(request, database, schema, table):
    logger.info(
        'table_data_view attempt: %s %s %s %s',
        request.user.email,
        database,
        schema,
        table,
    )

    log_event(
        request.user,
        EventLog.TYPE_DATASET_TABLE_DATA_DOWNLOAD,
        extra={
            'path': request.get_full_path(),
            'database': database,
            'schema': schema,
            'table': table,
        },
    )

    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    elif not can_access_schema_table(request.user, database, schema, table):
        return HttpResponseForbidden()
    elif not (
        view_exists(database, schema, table) or table_exists(database, schema, table)
    ):
        return HttpResponseNotFound()
    else:
        return table_data(request.user.email, database, schema, table)
