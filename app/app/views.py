import hashlib
import itertools
import logging

from django.contrib import (
    messages,
)
from django.conf import (
    settings,
)
from django.db import (
    connections,
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
    can_access_table,
    get_private_privilages,
    set_application_stopped,
)
from app.spawner import (
    spawner,
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
        with connections[database.memorable_name].cursor() as cur:
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


def _remove_duplicates(to_have_duplicates_removed):
    seen = set()
    seen_add = seen.add
    return [x for x in to_have_duplicates_removed if not (x in seen or seen_add(x))]
