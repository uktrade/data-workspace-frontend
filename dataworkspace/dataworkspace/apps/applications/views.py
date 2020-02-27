import hashlib
import random

import requests
from csp.decorators import csp_exempt
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from dataworkspace.apps.api_v1.views import (
    get_api_visible_application_instance_by_public_host,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from dataworkspace.apps.applications.utils import stop_spawner_and_application
from dataworkspace.apps.core.views import public_error_500_html_view

TOOL_LOADING_MESSAGES = [
    {
        'title': 'Principle 1 of the Data Protection Act 2018',
        'body': 'You must make sure that information is used fairly, lawfully and transparently.',
    },
    {
        'title': 'Principle 2 of the Data Protection Act 2018',
        'body': 'You must make sure that information is used for specified, explicit purposes.',
    },
    {
        'title': 'Principle 3 of the Data Protection Act 2018',
        'body': 'You must make sure that information is used in a way that is adequate, relevant '
        'and limited to only what is necessary.',
    },
    {
        'title': 'Principle 4 of the Data Protection Act 2018',
        'body': 'You must make sure that information is accurate and, where necessary, kept up to date.',
    },
    {
        'title': 'Principle 5 of the Data Protection Act 2018',
        'body': 'You must make sure that information is kept for no longer than is necessary.',
    },
    {
        'title': 'Principle 6 of the Data Protection Act 2018',
        'body': 'You must make sure that information is handled in a way that ensures appropriate '
        'security, including protection against unlawful or unauthorised processing, access, '
        'loss, destruction or damage.',
    },
]


@csp_exempt
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

    context = {
        'application_nice_name': application_instance.application_template.nice_name,
        'loading_message': TOOL_LOADING_MESSAGES[
            random.randint(0, len(TOOL_LOADING_MESSAGES) - 1)
        ],
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


def gitlab_api_v4(path, params=()):
    return requests.get(
        f'{settings.GITLAB_URL}api/v4/{path}',
        params=params,
        headers={'PRIVATE-TOKEN': settings.GITLAB_TOKEN},
    ).json()


def visualisations_html_view(request):
    if not request.user.has_perm('applications.develop_visualisations'):
        return HttpResponseForbidden()

    if not request.method == 'GET':
        return HttpResponse(status=405)

    return visualisations_html_GET(request)


def visualisations_html_GET(request):
    users = gitlab_api_v4(
        f'/users',
        params=(
            ('extern_uid', request.user.profile.sso_id),
            ('provider', 'oauth2_generic'),
        ),
    )
    has_gitlab_user = bool(users)

    # Something has really gone wrong if GitLab has multiple users with the
    # same SSO ID
    if len(users) > 1:
        return HttpResponse(status=500)

    if has_gitlab_user:
        params = (('sudo', users[0]['id']),)
    else:
        params = (('visibility', 'internal'),)

    projects = gitlab_api_v4(
        f'groups/{settings.GITLAB_VISUALISATIONS_GROUP}/projects',
        params=(('archived', 'false'),) + params,
    )

    def branch_sort_key(project):
        # Sort default branch first, the remaining in last commit order
        def _sort_key(branch):
            return (
                branch['name'] == project['default_branch'],
                branch['commit']['committed_date'],
                branch['name'],
            )

        return _sort_key

    project_branches = {
        project['id']: sorted(
            gitlab_api_v4(f'/projects/{project["id"]}/repository/branches'),
            key=branch_sort_key(project),
            reverse=True,
        )
        for project in projects
    }

    return render(
        request,
        'visualisations.html',
        {
            'gitlab_url': settings.GITLAB_URL,
            'has_gitlab_user': has_gitlab_user,
            'projects': projects,
            'project_branches': project_branches,
        },
        status=200,
    )
