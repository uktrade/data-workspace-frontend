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
        expected_total = application_instance.application_template.spawner_time
        now = datetime.datetime.now().timestamp()
        created = application_instance.created_date.timestamp()
        seconds_remaining_float = max(0, created + expected_total - now)
        seconds_remaining = math.ceil(seconds_remaining_float)
        seconds = seconds_remaining % 60
        minutes = int((seconds_remaining - seconds) / 60)
        memory = application_instance.memory
        cpu = application_instance.cpu
        cpu_memory_components = \
            ([str(int(cpu)/1024).rstrip('0').rstrip('.') + ' CPU'] if cpu is not None else []) + \
            ([str(int(memory)/1024).rstrip('0').rstrip('.') + ' GB of memory'] if memory is not None else [])
        cpu_memory = ' and '.join(cpu_memory_components)
        cpu_memory_string = ('with ' + cpu_memory) if cpu_memory else ''
        context = {
            'seconds_remaining_float': seconds_remaining_float,
            'time_remaining': f'{minutes}:{seconds:02}',
            'application_nice_name': application_instance.application_template.nice_name,
            'cpu_memory_string': cpu_memory_string,
        }
        return render(request, 'spawning.html', context, status=202)
