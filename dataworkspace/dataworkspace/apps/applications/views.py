import datetime
import hashlib
import math

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect

from dataworkspace.apps.api_v1.views import (
    get_api_visible_application_instance_by_public_host,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from dataworkspace.apps.applications.utils import stop_spawner_and_application

from dataworkspace.apps.core.views import public_error_500_html_view


def application_spawning_html_view(request, public_host):
    return (
        application_spawning_html_GET(request, public_host)
        if request.method == 'GET'
        else HttpResponse(status=405)
    )


def application_spawning_html_GET(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(
            public_host
        )
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
        cpu_memory_components = (
            [str(int(cpu) / 1024).rstrip('0').rstrip('.') + ' CPU']
            if cpu is not None
            else []
        ) + (
            [str(int(memory) / 1024).rstrip('0').rstrip('.') + ' GB of memory']
            if memory is not None
            else []
        )
        cpu_memory = ' and '.join(cpu_memory_components)
        cpu_memory_string = ('with ' + cpu_memory) if cpu_memory else ''
        context = {
            'seconds_remaining_float': seconds_remaining_float,
            'time_remaining': f'{minutes}:{seconds:02}',
            'application_nice_name': application_instance.application_template.nice_name,
            'cpu_memory_string': cpu_memory_string,
        }
        return render(request, 'spawning.html', context, status=202)


def tools_html_view(request):
    return (
        tools_html_POST(request)
        if request.method == 'POST'
        else tools_html_GET(request)
        if request.method == 'GET'
        else HttpResponse(status=405)
    )


def tools_html_GET(request):
    sso_id_hex = hashlib.sha256(
        str(request.user.profile.sso_id).encode('utf-8')
    ).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in ApplicationInstance.objects.filter(
            owner=request.user, state__in=['RUNNING', 'SPAWNING']
        )
    }

    def link(application_template):
        public_host = application_template.host_pattern.replace(
            '<user>', sso_id_hex_short
        )
        return f'{request.scheme}://{public_host}.{settings.APPLICATION_ROOT_DOMAIN}/'

    return render(
        request,
        'tools.html',
        {
            'applications': [
                {
                    'name': application_template.name,
                    'nice_name': application_template.nice_name,
                    'link': link(application_template),
                    'instance': application_instances.get(application_template, None),
                }
                for application_template in ApplicationTemplate.objects.all().order_by(
                    'name'
                )
                for application_link in [link(application_template)]
                if application_template.visible
            ],
            'appstream_url': settings.APPSTREAM_URL,
            'your_files_enabled': settings.YOUR_FILES_ENABLED,
        },
    )


def tools_html_POST(request):
    public_host = request.POST['public_host']
    redirect_target = {'root': 'root', 'applications:tools': 'applications:tools'}[
        request.POST['redirect_target']
    ]
    try:
        application_instance = ApplicationInstance.objects.get(
            owner=request.user,
            public_host=public_host,
            state__in=['RUNNING', 'SPAWNING'],
        )
    except ApplicationInstance.DoesNotExist:
        # The user could force a POST for any public_host, and will be able to
        # get the server to show this message, but this is acceptable since it
        # won't cause any harm
        messages.success(request, 'Stopped')
    else:
        stop_spawner_and_application(application_instance)
        messages.success(
            request, 'Stopped ' + application_instance.application_template.nice_name
        )
    return redirect(redirect_target)
