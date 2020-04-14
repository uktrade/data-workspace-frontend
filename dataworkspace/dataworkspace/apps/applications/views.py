import datetime
import hashlib
import json
import random
from urllib.parse import urlsplit

from csp.decorators import csp_exempt
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_text

from dataworkspace.apps.api_v1.views import (
    get_api_visible_application_instance_by_public_host,
)
from dataworkspace.apps.applications.gitlab import (
    DEVELOPER_ACCESS_LEVEL,
    gitlab_api_v4,
    gitlab_api_v4_with_status,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
    ApplicationTemplateUserPermission,
)
from dataworkspace.apps.applications.spawner import get_spawner
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
        'commit_id': application_instance.commit_id,
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
        app = application_template.host_basename
        return f'{request.scheme}://{app}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/'

    has_any_tool_perms = request.user.has_perm(
        'applications.start_all_applications'
    ) or request.user.has_perm('applications.access_appstream')
    view_file = 'tools.html' if has_any_tool_perms else 'tools-unauthorised.html'

    return render(
        request,
        view_file,
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


def visualisations_html_view(request):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    if not request.method == 'GET':
        return HttpResponse(status=405)

    return visualisations_html_GET(request)


def visualisations_html_GET(request):
    gitlab_users = gitlab_api_v4(
        'GET',
        f'/users',
        params=(
            ('extern_uid', request.user.profile.sso_id),
            ('provider', 'oauth2_generic'),
        ),
    )
    has_gitlab_user = bool(gitlab_users)

    # Something has really gone wrong if GitLab has multiple users with the
    # same SSO ID
    if len(gitlab_users) > 1:
        return HttpResponse(status=500)

    gitlab_url = (
        urlsplit(
            gitlab_api_v4('GET', f'groups/{settings.GITLAB_VISUALISATIONS_GROUP}')[
                'web_url'
            ]
        )
        ._replace(path='/', query='', fragment='')
        .geturl()
    )

    def get_projects(gitlab_user):
        gitlab_projects = gitlab_api_v4(
            'GET',
            f'groups/{settings.GITLAB_VISUALISATIONS_GROUP}/projects',
            params=(
                ('archived', 'false'),
                ('min_access_level', DEVELOPER_ACCESS_LEVEL),
                ('sudo', gitlab_user['id']),
            ),
        )
        application_templates = {
            application_template.gitlab_project_id: application_template
            for application_template in ApplicationTemplate.objects.filter(
                gitlab_project_id__in=[
                    gitlab_project['id'] for gitlab_project in gitlab_projects
                ]
            )
        }
        return [
            {
                'gitlab_project': gitlab_project,
                'manage_link': reverse(
                    'visualisations:branch',
                    kwargs={
                        'gitlab_project_id': gitlab_project['id'],
                        'branch_name': gitlab_project['default_branch'],
                    },
                ),
            }
            for gitlab_project in gitlab_projects
            if gitlab_project['id'] in application_templates
        ]

    return render(
        request,
        'visualisations.html',
        {
            'has_gitlab_user': has_gitlab_user,
            'gitlab_url': gitlab_url,
            'projects': get_projects(gitlab_users[0]) if has_gitlab_user else [],
        },
        status=200,
    )


def visualisation_branch_html_view(request, gitlab_project_id, branch_name):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not _visualisation_has_developer_access(request.user, gitlab_project):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_branch_html_GET(request, gitlab_project, branch_name)

    if request.method == 'POST':
        return visualisation_branch_html_POST(request, gitlab_project, branch_name)

    return HttpResponse(status=405)


def visualisation_branch_html_GET(request, gitlab_project, branch_name):
    branches = _visualisation_branches(gitlab_project)

    matching_branches = [branch for branch in branches if branch['name'] == branch_name]
    if len(matching_branches) > 1:
        raise Exception('Too many matching branches')
    if not matching_branches:
        raise Http404

    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )
    current_branch = matching_branches[0]
    latest_commit = current_branch['commit']
    latest_commit_link = f'{gitlab_project["web_url"]}/commit/{latest_commit["id"]}'
    latest_commit_preview_link = (
        f'{request.scheme}://{application_template.host_basename}--{latest_commit["short_id"]}'
        f'.{settings.APPLICATION_ROOT_DOMAIN}/'
    )
    latest_commit_date = datetime.datetime.strptime(
        latest_commit['committed_date'], '%Y-%m-%dT%H:%M:%S.%f%z'
    )
    latest_commit_tag_exists = get_spawner(application_template.spawner).tags_for_tag(
        json.loads(application_template.spawner_options),
        f'{application_template.host_basename}--{latest_commit["short_id"]}',
    )

    host_basename = application_template.host_basename
    production_link = (
        f'{request.scheme}://{host_basename}.{settings.APPLICATION_ROOT_DOMAIN}/'
    )
    tags = get_spawner(application_template.spawner).tags_for_tag(
        json.loads(application_template.spawner_options),
        application_template.host_basename,
    )
    production_commit_id = None
    for tag in tags:
        possible_host_basename, _, host_basename_or_commit_id = tag.rpartition('--')
        if possible_host_basename:
            production_commit_id = host_basename_or_commit_id
            break

    # It might not be good, UI-wise, to force the user to have to preview a
    # commit before it can be released. However, building a Docker image is
    # done via the preview link, so this is the quickest/easiest thing for
    # users to be able to release a new version of the visualisation
    must_preview_latest_commit_to_release = (
        current_branch['name'] == gitlab_project['default_branch']
        and not latest_commit_tag_exists
        and latest_commit['short_id'] != production_commit_id
    )
    can_release_latest_commit = (
        current_branch['name'] == gitlab_project['default_branch']
        and latest_commit_tag_exists
        and latest_commit['short_id'] != production_commit_id
    )
    latest_commit_is_released = latest_commit['short_id'] == production_commit_id

    return _render_visualisation(
        request,
        'visualisation_branch.html',
        gitlab_project,
        branches,
        current_menu_item='branches',
        template_specific_context={
            'production_link': production_link,
            'production_commit_id': production_commit_id,
            'current_branch': current_branch,
            'latest_commit': latest_commit,
            'latest_commit_link': latest_commit_link,
            'latest_commit_preview_link': latest_commit_preview_link,
            'latest_commit_date': latest_commit_date,
            'latest_commit_tag_exists': latest_commit_tag_exists,
            'can_release_latest_commit': can_release_latest_commit,
            'must_preview_latest_commit_to_release': must_preview_latest_commit_to_release,
            'latest_commit_is_released': latest_commit_is_released,
        },
    )


def visualisation_branch_html_POST(request, gitlab_project, branch_name):
    release_commit = request.POST['release-commit']
    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )
    get_spawner(application_template.spawner).retag(
        json.loads(application_template.spawner_options),
        f'{application_template.host_basename}--{release_commit}',
        application_template.host_basename,
    )

    try:
        application_instance = ApplicationInstance.objects.get(
            public_host=application_template.host_basename,
            state__in=['RUNNING', 'SPAWNING'],
        )
    except ApplicationInstance.DoesNotExist:
        pass
    else:
        stop_spawner_and_application(application_instance)

    messages.success(request, f'Released commit {release_commit} to production')

    return redirect(
        'visualisations:branch',
        gitlab_project_id=gitlab_project['id'],
        branch_name=branch_name,
    )


def visualisation_users_with_access_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not _visualisation_has_developer_access(request.user, gitlab_project):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_users_with_access_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_users_with_access_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def visualisation_users_with_access_html_GET(request, gitlab_project):
    branches = _visualisation_branches(gitlab_project)
    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )
    users = (
        get_user_model()
        .objects.filter(
            applicationtemplateuserpermission__application_template__gitlab_project_id=gitlab_project[
                'id'
            ]
        )
        .order_by('id')
    )

    return _render_visualisation(
        request,
        'visualisation_users_with_access.html',
        gitlab_project,
        branches,
        current_menu_item='users-with-access',
        template_specific_context={
            'application_template': application_template,
            'users': users,
        },
    )


def visualisation_users_with_access_html_POST(request, gitlab_project):
    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )
    user_id = request.POST['user-id']
    user = get_user_model().objects.get(id=user_id)

    content_type_id = ContentType.objects.get_for_model(user).pk

    with transaction.atomic():
        try:
            permission = ApplicationTemplateUserPermission.objects.get(
                user=user, application_template=application_template
            )
        except ApplicationTemplateUserPermission.DoesNotExist:
            # The permission could have been removed by another request. We
            # could surface an error, but the state is what the user wanted:
            # the user does not have access.
            pass
        else:
            permission.delete()

            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=content_type_id,
                object_id=user.id,
                object_repr=force_text(user),
                action_flag=CHANGE,
                change_message=f'Removed visualisation {application_template} permission',
            )

    messages.success(
        request,
        f'{user.get_full_name()} can no longer view the ‘{gitlab_project["name"]}’ visualisation.',
    )
    return redirect(
        'visualisations:users-with-access', gitlab_project_id=gitlab_project['id']
    )


def visualisation_users_give_access_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not _visualisation_has_developer_access(request.user, gitlab_project):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_users_give_access_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_users_give_access_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def visualisation_users_give_access_html_GET(request, gitlab_project):
    branches = _visualisation_branches(gitlab_project)
    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )

    return _render_visualisation(
        request,
        'visualisation_users_give_access.html',
        gitlab_project,
        branches,
        current_menu_item='users-give-access',
        template_specific_context={'application_template': application_template},
    )


def visualisation_users_give_access_html_POST(request, gitlab_project):
    branches = _visualisation_branches(gitlab_project)
    application_template = ApplicationTemplate.objects.get(
        gitlab_project_id=gitlab_project['id']
    )

    email_address = request.POST['email-address'].strip().lower()

    def error(email_address_error):
        return _render_visualisation(
            request,
            'visualisation_users_give_access.html',
            gitlab_project,
            branches,
            current_menu_item='users-give-access',
            template_specific_context={
                'email_address': email_address,
                'email_address_error': email_address_error,
                'application_template': application_template,
            },
        )

    if not email_address:
        return error('Enter the user\'s email address')

    try:
        EmailValidator()(email_address)
    except ValidationError:
        return error(
            'Enter the user\'s email address in the correct format, like name@example.com'
        )

    User = get_user_model()

    try:
        user = User.objects.get(email=email_address)
    except User.DoesNotExist:
        return error('The user must have previously visisted Data Workspace')

    content_type_id = ContentType.objects.get_for_model(user).pk

    with transaction.atomic():
        try:
            ApplicationTemplateUserPermission.objects.create(
                user=user, application_template=application_template
            )
        except IntegrityError:
            return error(f'{user.get_full_name()} already has access')

        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=content_type_id,
            object_id=user.id,
            object_repr=force_text(user),
            action_flag=CHANGE,
            change_message=f'Added visualisation {application_template} permission',
        )

    messages.success(
        request,
        f'{user.get_full_name()} now has view access to {gitlab_project["name"]}',
    )
    return redirect(
        'visualisations:users-give-access', gitlab_project_id=gitlab_project['id']
    )


def _visualisation_gitlab_project(gitlab_project_id):
    gitlab_project, status = gitlab_api_v4_with_status(
        'GET', f'projects/{gitlab_project_id}'
    )
    if status == 404:
        raise Http404
    if status != 200:
        raise Exception(
            f'Unable to find GitLab project {gitlab_project_id}: received {status}'
        )

    return gitlab_project


def _visualisation_has_developer_access(user, gitlab_project):
    gitlab_users, status = gitlab_api_v4_with_status(
        'GET',
        f'/users',
        params=(('extern_uid', user.profile.sso_id), ('provider', 'oauth2_generic')),
    )

    if status != 200:
        raise Exception(
            f'Unable to find GitLab user for {user.profile.sso_id}: received {status}'
        )

    if len(gitlab_users) > 1:
        raise Exception(f'Too many GitLab users matching {user.profile.sso_id}')

    if not gitlab_users:
        return False

    gitlab_user = gitlab_users[0]
    gitlab_project_users = gitlab_api_v4(
        'GET',
        f'/projects/{gitlab_project["id"]}/members/all',
        params=(('user_ids', str(gitlab_user['id'])),),
    )

    return True in (
        gitlab_project_user['id'] == gitlab_user['id']
        and gitlab_project_user['access_level'] >= int(DEVELOPER_ACCESS_LEVEL)
        for gitlab_project_user in gitlab_project_users
    )


def _visualisation_branches(gitlab_project):
    # Sort default branch first, the remaining in last commit order
    def branch_sort_key(branch):
        return (
            branch['name'] == gitlab_project['default_branch'],
            branch['commit']['committed_date'],
            branch['name'],
        )

    return sorted(
        gitlab_api_v4('GET', f'/projects/{gitlab_project["id"]}/repository/branches'),
        key=branch_sort_key,
        reverse=True,
    )


def _render_visualisation(
    request,
    template,
    gitlab_project,
    branches,
    current_menu_item,
    template_specific_context,
):
    # For templates that inherit from _visualisation.html. This is factored
    # out, in a way so that any context variables required, but not passed from
    # the view have a chance to be caught by linting
    return render(
        request,
        template,
        {
            'gitlab_project': gitlab_project,
            'branches': branches,
            'current_menu_item': current_menu_item,
            **template_specific_context,
        },
        status=200,
    )
