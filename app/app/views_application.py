import datetime
import hashlib
import json
import logging
import math

from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import (
    render,
)

from app.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from app.shared import (
    new_private_database_credentials,
    set_application_stopped,
)
from app.spawner import (
    get_spawner,
    spawn,
)
from app.views_error import (
    public_error_500_html_view,
)

logger = logging.getLogger('app')


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


def get_api_visible_application_instance_by_public_host(public_host):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.get(
        public_host=public_host, state__in=['RUNNING', 'SPAWNING'],
    )


def get_running_applications():
    return ApplicationInstance.objects.filter(
        state='RUNNING',
    )


def api_application_dict(application_instance):
    spawner_state = get_spawner(application_instance.application_template.spawner).state(
        application_instance.spawner_application_template_options,
        application_instance.created_date.replace(tzinfo=None),
        application_instance.spawner_application_instance_id,
        application_instance.public_host,
    )

    # Only pass through the database state if the spawner is running,
    # Otherwise, we are in an error condition, and so return the spawner
    # state, so the client (i.e. the proxy) knows to take action
    api_state = \
        application_instance.state if spawner_state == 'RUNNING' else \
        spawner_state

    template_name = application_instance.application_template.name
    sso_id_hex = hashlib.sha256(str(application_instance.owner.profile.sso_id).encode('utf-8')).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    return {
        'proxy_url': application_instance.proxy_url,
        'state': api_state,
        'user': sso_id_hex_short,
        'name': template_name,
    }


def applications_api_view(request):
    return \
        applications_api_GET(request) if request.method == 'GET' else \
        JsonResponse({}, status=405)


def applications_api_GET(request):
    return JsonResponse({
        'applications': [
            api_application_dict(application)
            for application in get_running_applications()
        ]
    }, status=200)


def application_api_view(request, public_host):
    return \
        JsonResponse({}, status=403) if not application_api_is_allowed(request, public_host) else \
        application_api_GET(request, public_host) if request.method == 'GET' else \
        application_api_PUT(request, public_host) if request.method == 'PUT' else \
        application_api_PATCH(request, public_host) if request.method == 'PATCH' else \
        application_api_DELETE(request, public_host) if request.method == 'DELETE' else \
        JsonResponse({}, status=405)


def application_api_is_allowed(request, public_host):
    _, _, owner_sso_id_hex = public_host.partition('-')

    request_sso_id_hex = hashlib.sha256(
        str(request.user.profile.sso_id).encode('utf-8')).hexdigest()

    return owner_sso_id_hex == request_sso_id_hex[:8] and request.user.has_perm('app.start_all_applications')


def application_api_GET(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=404)

    return JsonResponse(api_application_dict(application_instance), status=200)


def application_api_PUT(request, public_host):
    # A transaction is unnecessary: the single_running_or_spawning_integrity
    # key prevents duplicate spawning/running applications at the same
    # public host
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        pass
    else:
        return JsonResponse({'message': 'Application instance already exists'}, status=409)

    application_template_name, _, _ = public_host.partition('-')

    try:
        application_template = ApplicationTemplate.objects.get(
            name=application_template_name,
        )
    except ApplicationTemplate.DoesNotExist:
        return JsonResponse({'message': 'Application template does not exist'}, status=400)

    credentials = new_private_database_credentials(request.user)

    application_instance = ApplicationInstance.objects.create(
        owner=request.user,
        application_template=application_template,
        spawner=application_template.spawner,
        spawner_application_template_options=application_template.spawner_options,
        spawner_application_instance_id=json.dumps({}),
        public_host=public_host,
        state='SPAWNING',
        single_running_or_spawning_integrity=public_host,
    )

    spawn.delay(
        application_template.spawner,
        request.user.email, str(request.user.profile.sso_id), application_instance.id,
        application_template.spawner_options, credentials)

    return JsonResponse(api_application_dict(application_instance), status=200)


def application_api_PATCH(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=404)

    state = json.loads(request.body)['state']

    if state != 'RUNNING':
        return JsonResponse({}, status=400)

    application_instance.state = state
    application_instance.save()

    return JsonResponse({}, status=200)


def application_api_DELETE(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=200)

    set_application_stopped(application_instance)

    return JsonResponse({}, status=200)
