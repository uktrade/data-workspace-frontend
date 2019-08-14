import datetime
import math

from django.http import HttpResponse
from django.shortcuts import render

from dataworkspace.apps.api_v1.views import get_api_visible_application_instance_by_public_host
from dataworkspace.apps.applications.models import ApplicationInstance

from dataworkspace.apps.core.views import public_error_500_html_view


def application_spawning_html_view(request, public_host):
    return \
        application_spawning_html_GET(request, public_host) if request.method == 'GET' else \
        HttpResponse(status=405)


def application_spawning_html_GET(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return public_error_500_html_view(request)
    else:
        # There is some duplication between this and the front end, but
        # we avoid the occasional flash if missing content before the
        # front end renders the time remaining
        expected_total = 120
        now = datetime.datetime.now().timestamp()
        created = application_instance.created_date.timestamp()
        seconds_remaining_float = max(0, created + expected_total - now)
        seconds_remaining = math.ceil(seconds_remaining_float)
        seconds = seconds_remaining % 60
        minutes = int((seconds_remaining - seconds) / 60)
        context = {
            'seconds_remaining_float': seconds_remaining_float,
            'time_remaining': f'{minutes}:{seconds:02}',
            'application_nice_name': application_instance.application_template.nice_name,
        }
        return render(request, 'spawning.html', context, status=202)
