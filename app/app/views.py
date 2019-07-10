import hashlib
import logging

from django.contrib import (
    messages,
)
from django.conf import (
    settings,
)
from django.http import (
    HttpResponse,
)
from django.shortcuts import (
    redirect,
    render,
)

from app.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from app.shared import (
    stop_spawner_and_application,
)
from app.spawner import (
    get_spawner,
)

from app.views_catalogue import (
    get_all_datagroups_viewmodel,
)

logger = logging.getLogger('app')


def root_view(request):
    return \
        root_view_GET(request) if request.method == 'GET' else \
        root_view_POST(request) if request.method == 'POST' else \
        HttpResponse(status=405)


def root_view_GET(request):
    sso_id_hex = hashlib.sha256(str(request.user.profile.sso_id).encode('utf-8')).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in filter_api_visible_application_instances_by_owner(request.user)
    }

    def can_stop(application_template):
        application_instance = application_instances.get(application_template, None)
        return \
            application_instance is not None and get_spawner(application_instance.spawner).can_stop(
                application_instance.spawner_application_template_options,
                application_instance.spawner_application_instance_id,
            )

    context = {
        'applications': [
            {
                'name': application_template.name,
                'nice_name': application_template.nice_name,
                'link': f'{request.scheme}://{application_template.name}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/',
                'instance': application_instances.get(application_template, None),
                'can_stop': can_stop(application_template),
            }
            for application_template in ApplicationTemplate.objects.all().order_by('name')
        ],
        'appstream_url': settings.APPSTREAM_URL,
        'groupings': get_all_datagroups_viewmodel()
    }
    return render(request, 'root.html', context)


def root_view_POST(request):
    application_instance_id = request.POST['application_instance_id']
    application_instance = ApplicationInstance.objects.get(
        id=application_instance_id,
        owner=request.user,
        state__in=['RUNNING', 'SPAWNING'],
    )

    if application_instance.state != 'STOPPED':
        stop_spawner_and_application(application_instance)

    messages.success(request, 'Stopped ' + application_instance.application_template.nice_name)
    return redirect('root')


def filter_api_visible_application_instances_by_owner(owner):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.filter(owner=owner, state__in=['RUNNING', 'SPAWNING'])


def _flatten(to_flatten):
    return [
        item
        for sub_list in to_flatten
        for item in sub_list
    ]
