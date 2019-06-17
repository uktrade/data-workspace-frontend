import datetime
import hashlib
import itertools
import json
import logging
import math
import boto3

from django.contrib import (
    messages,
)
from django.contrib.auth import (
    get_user_model,
)
from django.conf import (
    settings,
)
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import (
    redirect,
    render,
)
from psycopg2 import (
    connect,
)

from app.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from app.shared import (
    can_access_table,
    database_dsn,
    get_private_privilages,
    new_private_database_credentials,
)
from app.spawner import (
    spawner,
)
from app.views_error import (
    public_error_500_html_view,
)

logger = logging.getLogger('app')


def root_view(request):
    return \
        root_view_GET(request) if request.method == 'GET' else \
        root_view_POST(request) if request.method == 'POST' else \
        HttpResponse(status=405)


def root_view_GET(request):
    def tables_in_schema(cur, schema):
        logger.info('tables_in_schema: %s', schema)
        cur.execute("""
            SELECT
                tablename
            FROM
                pg_tables
            WHERE
                schemaname = %s
        """, (schema, ))
        results = [result[0] for result in cur.fetchall()]
        logger.info('tables_in_schema: %s %s', schema, results)
        return results

    def allowed_tables_for_database_that_exist(database, database_privilages):
        logger.info('allowed_tables_for_database_that_exist: %s %s', database, database_privilages)
        with \
                connect(database_dsn(settings.DATABASES_DATA[database.memorable_name])) as conn, \
                conn.cursor() as cur:
            return [
                (database.memorable_name, privilage.schema, table)
                for privilage in database_privilages
                for table in tables_in_schema(cur, privilage.schema)
                if can_access_table(database_privilages, database.memorable_name, privilage.schema, table)
            ]

    privilages = get_private_privilages(request.user)
    privilages_by_database = itertools.groupby(privilages, lambda privilage: privilage.database)

    sso_id_hex = hashlib.sha256(str(request.user.profile.sso_id).encode('utf-8')).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in filter_api_visible_application_instances_by_owner(request.user)
    }

    def can_stop(application_template):
        application_instance = application_instances.get(application_template, None)
        return \
            application_instance is not None and spawner(application_instance.spawner).can_stop(
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
        'database_schema_tables': _remove_duplicates(_flatten([
            allowed_tables_for_database_that_exist(database, list(database_privilages))
            for database, database_privilages in privilages_by_database
        ])),
        'appstream_url': settings.APPSTREAM_URL,
        'support_url': settings.SUPPORT_URL,
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
        spawner(application_instance.spawner).stop(
            application_instance.spawner_application_template_options,
            application_instance.spawner_application_instance_id,
        )
        set_application_stopped(application_instance)

    messages.success(request, 'Stopped ' + application_instance.application_template.nice_name)
    return redirect('root')


def appstream_view(request):
    User = get_user_model()

    client = boto3.client(
        'appstream',
        aws_access_key_id=settings.APPSTREAM_AWS_ACCESS_KEY,
        aws_secret_access_key=settings.APPSTREAM_AWS_SECRET_KEY,
        region_name=settings.APPSTREAM_AWS_REGION
    )

    fleet_status = client.describe_fleets(
        Names=[settings.APPSTREAM_FLEET_NAME, ]
    )

    for item in fleet_status['Fleets']:
        ComputeCapacityStatus = item['ComputeCapacityStatus']

    app_sessions = client.describe_sessions(
        StackName=settings.APPSTREAM_STACK_NAME,
        FleetName=settings.APPSTREAM_FLEET_NAME
    )

    app_sessions_users = [
        (app_session, User.objects.get(profile__sso_id=app_session['UserId']))
        for app_session in app_sessions['Sessions']
    ]

    context = {
        'fleet_status': ComputeCapacityStatus,
        'app_sessions_users': app_sessions_users,
    }

    return render(request, 'appstream.html', context)


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


def filter_api_visible_application_instances_by_owner(owner):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.filter(owner=owner, state__in=['RUNNING', 'SPAWNING'])


def api_application_dict(application_instance):
    spawner_state = spawner(application_instance.application_template.spawner).state(
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

    return {
        'proxy_url': application_instance.proxy_url,
        'state': api_state,
    }


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

    spawner_class = spawner(application_template.spawner)
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

    def set_url(proxy_url):
        application_instance.proxy_url = proxy_url
        application_instance.save()

    def set_id(spawner_application_instance_id):
        application_instance.spawner_application_instance_id = spawner_application_instance_id
        application_instance.save()

    spawner_class.spawn(
        request.user.email, request.user.profile.sso_id, application_instance.id,
        application_template.spawner_options, credentials, set_id, set_url)

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


def set_application_stopped(application_instance):
    application_instance.state = 'STOPPED'
    application_instance.single_running_or_spawning_integrity = str(application_instance.id)
    application_instance.save()


def _flatten(to_flatten):
    return [
        item
        for sub_list in to_flatten
        for item in sub_list
    ]


def _remove_duplicates(to_have_duplicates_removed):
    seen = set()
    seen_add = seen.add
    return [x for x in to_have_duplicates_removed if not (x in seen or seen_add(x))]
