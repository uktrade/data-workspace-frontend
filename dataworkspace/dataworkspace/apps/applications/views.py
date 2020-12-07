import datetime


import itertools
import json
import random
import re
from contextlib import closing
from io import StringIO
from urllib.parse import urlsplit, urlencode

from csp.decorators import csp_exempt, csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.views.decorators.http import require_GET
from django.views.generic.edit import UpdateView
from waffle import flag_is_active

from dataworkspace.apps.api_v1.views import (
    get_api_visible_application_instance_by_public_host,
)
from dataworkspace.apps.applications.forms import (
    VisualisationsUICatalogueItemForm,
    VisualisationApprovalForm,
)
from dataworkspace.apps.applications.gitlab import (
    DEVELOPER_ACCESS_LEVEL,
    gitlab_api_v4,
    gitlab_api_v4_with_status,
    gitlab_has_developer_access,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationTemplate,
    ToolTemplate,
    UserToolConfiguration,
    VisualisationApproval,
    VisualisationTemplate,
)
from dataworkspace.apps.applications.utils import (
    application_options,
    fetch_visualisation_log_events,
    get_quicksight_dashboard_name_url,
    sync_quicksight_permissions,
    log_visualisation_view,
)
from dataworkspace.apps.applications.spawner import get_spawner
from dataworkspace.apps.applications.utils import stop_spawner_and_application
from dataworkspace.apps.core.utils import (
    source_tables_for_app,
    source_tables_for_user,
    stable_identification_suffix,
)
from dataworkspace.apps.core.views import public_error_500_html_view
from dataworkspace.apps.datasets.models import (
    MasterDataset,
    DataSetApplicationTemplatePermission,
    VisualisationCatalogueItem,
    VisualisationUserPermission,
    VisualisationLink,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.notify import decrypt_token, send_email
from dataworkspace.utils import DATA_EXPLORER_FLAG
from dataworkspace.zendesk import update_zendesk_ticket

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


@csp_exempt
def application_running_html_view(request, public_host):
    return (
        application_running_html_GET(request, public_host)
        if request.method == 'GET'
        else HttpResponse(status=405)
    )


def application_running_html_GET(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(
            public_host
        )
    except ApplicationInstance.DoesNotExist:
        return public_error_500_html_view(request)

    port = urlsplit(application_instance.proxy_url).port
    context = {
        'visualisation_src': f'{request.scheme}://{application_instance.public_host}--{port}.'
        f'{settings.APPLICATION_ROOT_DOMAIN}/',
        'nice_name': application_instance.application_template.nice_name,
        'wrap': application_instance.application_template.wrap,
    }

    return render(request, 'running.html', context, status=200)


def tools_html_view(request):
    return (
        tools_html_POST(request)
        if request.method == 'POST'
        else tools_html_GET(request)
        if request.method == 'GET'
        else HttpResponse(status=405)
    )


def tools_html_GET(request):
    sso_id_hex_short = stable_identification_suffix(
        str(request.user.profile.sso_id), short=True
    )

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in ApplicationInstance.objects.filter(
            owner=request.user, state__in=['RUNNING', 'SPAWNING']
        )
    }

    def link(application_template):
        app = application_template.host_basename
        return f'{request.scheme}://{app}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/'

    return render(
        request,
        'tools.html',
        {
            'applications': [
                {
                    'host_basename': application_template.host_basename,
                    'nice_name': application_template.nice_name,
                    'link': link(application_template),
                    'instance': application_instances.get(application_template, None),
                    'summary': application_template.application_summary,
                    'help_link': application_template.application_help_link,
                    'tool_configuration': application_template.user_tool_configuration.filter(
                        user=request.user
                    ).first()
                    or UserToolConfiguration.default_config(),
                }
                for application_template in ApplicationTemplate.objects.all()
                .filter(visible=True, application_type='TOOL')
                .order_by('nice_name')
            ],
            'appstream_url': settings.APPSTREAM_URL,
            'quicksight_url': reverse('applications:quicksight_redirect'),
            'your_files_enabled': settings.YOUR_FILES_ENABLED,
            'show_new_data_explorer': flag_is_active(request, DATA_EXPLORER_FLAG),
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


@csp_update(
    frame_src=settings.QUICKSIGHT_DASHBOARD_HOST,
    frame_ancestors=settings.VISUALISATION_EMBED_DOMAINS,
)
def _get_embedded_quicksight_dashboard(request, dashboard_id):
    dashboard_name, dashboard_url = get_quicksight_dashboard_name_url(
        dashboard_id, request.user
    )

    extra_params = urlencode(
        [("punyCodeEmbedOrigin", f"{request.scheme}://{request.get_host()}/")]
    )

    context = {
        'visualisation_src': f'{dashboard_url}&{extra_params}',
        'nice_name': dashboard_name,
        'wrap': 'IFRAME_WITH_VISUALISATIONS_HEADER',
    }

    return render(request, 'running.html', context, status=200)


@require_GET
def quicksight_start_polling_sync_and_redirect(request):
    if not request.user.has_perm('applications.access_quicksight'):
        return HttpResponse(status=403)

    sync_quicksight_permissions.delay(
        user_sso_ids_to_update=(request.user.profile.sso_id,),
        poll_for_user_creation=True,
    )

    return redirect(settings.QUICKSIGHT_SSO_URL)


@require_GET
def visualisation_link_html_view(request, link_id):
    try:
        visualisation_link = VisualisationLink.objects.get(id=link_id)
    except VisualisationLink.DoesNotExist:
        return HttpResponse(status=404)

    if not visualisation_link.visualisation_catalogue_item.user_has_access(
        request.user
    ):
        return HttpResponse(status=403)

    identifier = visualisation_link.identifier
    if visualisation_link.visualisation_type == 'QUICKSIGHT':
        log_visualisation_view(
            visualisation_link,
            request.user,
            event_type=EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
        )
        return _get_embedded_quicksight_dashboard(request, identifier)
    elif visualisation_link.visualisation_type == 'DATASTUDIO':
        log_visualisation_view(
            visualisation_link,
            request.user,
            event_type=EventLog.TYPE_VIEW_DATASTUDIO_VISUALISATION,
        )
        return redirect(identifier)

    return HttpResponse(
        status=500,
        content=f'Unsupported visualisation type: {visualisation_link.visualisation_type}'.encode(
            'utf8'
        ),
    )


def visualisations_html_view(request):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    if not request.method == 'GET':
        return HttpResponse(status=405)

    return visualisations_html_GET(request)


def visualisations_html_GET(request):
    gitlab_users = gitlab_api_v4(
        'GET',
        '/users',
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
        gitlab_projects_including_non_visualisation = gitlab_api_v4(
            'GET',
            'projects',
            params=(
                ('archived', 'false'),
                ('min_access_level', DEVELOPER_ACCESS_LEVEL),
                ('sudo', gitlab_user['id']),
                ('per_page', '100'),
            ),
        )
        gitlab_projects = [
            gitlab_project
            for gitlab_project in gitlab_projects_including_non_visualisation
            if 'visualisation' in [tag.lower() for tag in gitlab_project['tag_list']]
        ]
        return sorted(
            [
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
            ],
            key=lambda d: d['gitlab_project']['name'].lower(),
        )

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

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
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

    application_template = _application_template(gitlab_project)
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
        application_options(application_template),
        f'{application_template.host_basename}--{latest_commit["short_id"]}',
    )

    host_basename = application_template.host_basename
    production_link = (
        f'{request.scheme}://{host_basename}.{settings.APPLICATION_ROOT_DOMAIN}/'
    )
    tags = get_spawner(application_template.spawner).tags_for_tag(
        application_options(application_template), application_template.host_basename
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
        application_template,
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
    application_template = _application_template(gitlab_project)
    get_spawner(application_template.spawner).retag(
        application_options(application_template),
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

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_users_with_access_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_users_with_access_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def visualisation_users_with_access_html_GET(request, gitlab_project):
    branches = _visualisation_branches(gitlab_project)
    application_template = _application_template(gitlab_project)
    users = (
        get_user_model()
        .objects.filter(
            visualisationuserpermission__visualisation__visualisation_template__gitlab_project_id=gitlab_project[
                'id'
            ]
        )
        .order_by('id')
    )

    return _render_visualisation(
        request,
        'visualisation_users_with_access.html',
        gitlab_project,
        application_template,
        branches,
        current_menu_item='users-with-access',
        template_specific_context={
            'application_template': application_template,
            'users': users,
        },
    )


def visualisation_users_with_access_html_POST(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    visualisation_catalogue_item = VisualisationCatalogueItem.objects.get(
        visualisation_template=application_template
    )
    user_id = request.POST['user-id']
    user = get_user_model().objects.get(id=user_id)

    content_type_id = ContentType.objects.get_for_model(user).pk

    with transaction.atomic():
        try:
            permission = VisualisationUserPermission.objects.get(
                user=user, visualisation=visualisation_catalogue_item
            )
        except VisualisationUserPermission.DoesNotExist:
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
                object_repr=force_str(user),
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

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    token = request.GET.get("token")
    token_data = decrypt_token(token.encode('utf-8')) if token else {}

    if request.method == 'GET':
        return visualisation_users_give_access_html_GET(
            request, gitlab_project, token_data
        )

    if request.method == 'POST':
        return visualisation_users_give_access_html_POST(
            request, gitlab_project, token_data
        )

    return HttpResponse(status=405)


def visualisation_users_give_access_html_GET(request, gitlab_project, token_data):
    branches = _visualisation_branches(gitlab_project)
    application_template = _application_template(gitlab_project)

    return _render_visualisation(
        request,
        'visualisation_users_give_access.html',
        gitlab_project,
        application_template,
        branches,
        current_menu_item='users-give-access',
        template_specific_context={
            'application_template': application_template,
            'email_address': token_data.get("email", ""),
        },
    )


def visualisation_users_give_access_html_POST(request, gitlab_project, token_data):
    branches = _visualisation_branches(gitlab_project)
    application_template = _application_template(gitlab_project)
    visualisation_catalogue_item = VisualisationCatalogueItem.objects.get(
        visualisation_template=application_template
    )

    email_address = request.POST['email-address'].strip().lower()

    def error(email_address_error):
        return _render_visualisation(
            request,
            'visualisation_users_give_access.html',
            gitlab_project,
            application_template,
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
        return error('The user must have previously visited Data Workspace')

    content_type_id = ContentType.objects.get_for_model(user).pk

    try:
        with transaction.atomic():
            VisualisationUserPermission.objects.create(
                user=user, visualisation=visualisation_catalogue_item
            )
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=content_type_id,
                object_id=user.id,
                object_repr=force_str(user),
                action_flag=CHANGE,
                change_message=f'Added visualisation {application_template} permission',
            )
    except IntegrityError:
        return error(f'{user.get_full_name()} already has access')

    if email_address == token_data.get("email", "").strip().lower():
        update_zendesk_ticket(
            token_data["ticket"],
            comment=f"Access granted by {request.user.email}",
            status="solved",
        )

    catalogue_item = VisualisationCatalogueItem.objects.get(
        visualisation_template=application_template
    )

    if catalogue_item.published:
        send_email(
            settings.NOTIFY_VISUALISATION_ACCESS_GRANTED_TEMPLATE_ID,
            email_address,
            personalisation={
                "visualisation_name": catalogue_item.name,
                "enquiries_contact_email": catalogue_item.enquiries_contact.email,
            },
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


def _application_template(gitlab_project):
    try:
        return ApplicationTemplate.objects.get(gitlab_project_id=gitlab_project['id'])
    except ApplicationTemplate.DoesNotExist:
        pass

    # We attempt to find a string similar to the GitLab project name that can
    # be both a hostname and a path component: lowercase letters, numbers and
    # hyphens can be in both. To KISS we don't allow characters that require
    # punycoding / urlencoding, and we use a combination of filtering and
    # conversion to achieve this. The process is tailored for typical English
    # projects names: for other languages it will likely not give great
    # results. However:
    # - project names _will_ be in English for the foreseeable future
    # - in many cases people don't even look at the URL
    # - it can be changed by an admin if it needs to be
    # - there is a plan to make it changable by the user
    name_1 = gitlab_project['name']
    name_2 = name_1.lower()
    name_3 = re.sub(r'[_\s]', '-', name_2)
    name_4 = re.sub(r'[^a-z0-9\-]', '', name_3)
    name_5 = name_4.strip('-')
    name_6 = re.sub('-+', '-', name_5)
    path_and_dns_safe_root = name_6

    # Attempt to make ApplicationTemplate.host_basename and
    # VisualisationCatalogueItem.slug the same by trying several suffixes.
    # If we can't find a host_basename or slug that is available for both,
    # fail with an IntegrityError and return a 500 to the user. If there are
    # really so many projects with such similar names to cause this, suspect
    # that user frustration + support request is the best option, because
    # something unexpected is happening that should be addressed
    max_attempts = 20
    for i in range(0, max_attempts):
        if i == 0:
            suffix = ''
        else:
            suffix = '-' + str(i)
        path_and_dns_safe_name = path_and_dns_safe_root + suffix

        try:
            with transaction.atomic():
                visualisation_template = ApplicationTemplate.objects.create(
                    host_basename=path_and_dns_safe_name,
                    nice_name=gitlab_project['name'],
                    spawner='FARGATE',
                    spawner_time=120,
                    spawner_options='{}',
                    application_type='VISUALISATION',
                    gitlab_project_id=gitlab_project['id'],
                    wrap='FULL_HEIGHT_IFRAME',
                    visible=False,
                )
                VisualisationCatalogueItem.objects.create(
                    name=gitlab_project['name'],
                    slug=path_and_dns_safe_name,
                    short_description=gitlab_project['description'],
                    visualisation_template=visualisation_template,
                    user_access_type='REQUIRES_AUTHORIZATION',
                )
                return visualisation_template
        except IntegrityError as integrity_error:
            if i < max_attempts - 1:
                continue

            # We could have raised an IntegrityError if a template with
            # gitlab_project['id'] has been created by a parallel request, in
            # which case there is no need to fail: we can query again to try
            # to find it. Only if it again can't be found do we actually fail
            try:
                return ApplicationTemplate.objects.get(
                    gitlab_project_id=gitlab_project['id']
                )
            except ApplicationTemplate.DoesNotExist:
                raise integrity_error


def _render_visualisation(
    request,
    template,
    gitlab_project,
    application_template,
    branches,
    current_menu_item,
    template_specific_context,
    status=200,
):
    # For templates that inherit from _visualisation.html. This is factored
    # out, in a way so that any context variables required, but not passed from
    # the view have a chance to be caught by linting
    catalogue_item = _get_visualisation_catalogue_item_for_gitlab_project(
        gitlab_project
    )
    return render(
        request,
        template,
        {
            'gitlab_project': gitlab_project,
            'catalogue_item': catalogue_item,
            'show_users_section': catalogue_item.user_access_type
            == 'REQUIRES_AUTHORIZATION',
            'branches': branches,
            'current_menu_item': current_menu_item,
            **template_specific_context,
        },
        status=status,
    )


def visualisation_catalogue_item_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_catalogue_item_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_catalogue_item_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def _get_visualisation_catalogue_item_for_gitlab_project(gitlab_project):
    catalogue_item = None

    application_template = _application_template(gitlab_project)

    try:
        catalogue_item = VisualisationCatalogueItem.objects.get(
            visualisation_template=application_template
        )
    except VisualisationCatalogueItem.DoesNotExist:
        pass

    return catalogue_item


def visualisation_catalogue_item_html_GET(request, gitlab_project):
    catalogue_item = _get_visualisation_catalogue_item_for_gitlab_project(
        gitlab_project
    )
    form = VisualisationsUICatalogueItemForm(instance=catalogue_item)

    # We don't want client-side validation on this field, so we remove it - but only for the GET request.
    form.fields['short_description'].required = False

    return _render_visualisation(
        request,
        'visualisation_catalogue_item.html',
        gitlab_project,
        catalogue_item.visualisation_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='catalogue-item',
        template_specific_context={'form': form},
    )


def visualisation_catalogue_item_html_POST(request, gitlab_project):
    catalogue_item = _get_visualisation_catalogue_item_for_gitlab_project(
        gitlab_project
    )
    user_access_type = catalogue_item.user_access_type
    form = VisualisationsUICatalogueItemForm(request.POST, instance=catalogue_item)
    if form.is_valid():
        with transaction.atomic():
            form.save()
            if user_access_type != catalogue_item.user_access_type:
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=ContentType.objects.get_for_model(
                        get_user_model()
                    ).pk,
                    object_id=catalogue_item.visualisation_template.pk,
                    object_repr=force_str(catalogue_item.visualisation_template),
                    action_flag=CHANGE,
                    change_message=(
                        f"Changed user_access_type on {catalogue_item.visualisation_template} "
                        f"to: {catalogue_item.user_access_type}"
                    ),
                )
        return redirect(
            'visualisations:catalogue-item', gitlab_project_id=gitlab_project['id']
        )

    form_errors = [
        (field.id_for_label, field.errors[0]) for field in form if field.errors
    ]

    return _render_visualisation(
        request,
        'visualisation_catalogue_item.html',
        gitlab_project,
        catalogue_item.visualisation_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='catalogue-item',
        template_specific_context={"form": form, "form_errors": form_errors},
        status=400 if form_errors else 200,
    )


def visualisation_approvals_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_approvals_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_approvals_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def visualisation_approvals_html_GET(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    approvals = VisualisationApproval.objects.filter(
        visualisation=application_template, approved=True
    ).all()

    approval = next(filter(lambda a: a.approver == request.user, approvals), None)

    form = VisualisationApprovalForm(
        instance=approval,
        initial={
            "visualisation": application_template,
            "approver": request.user,
            "approved": False,
        },
    )

    return _render_visualisation(
        request,
        'visualisation_approvals.html',
        gitlab_project,
        application_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='approvals',
        template_specific_context={
            'approvals': approvals,
            'already_approved': approval.approved if approval else False,
            'form': form,
        },
    )


def visualisation_approvals_html_POST(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    approvals = VisualisationApproval.objects.filter(
        visualisation=application_template, approved=True
    ).all()

    approval = next(filter(lambda a: a.approver == request.user, approvals), None)

    form = VisualisationApprovalForm(
        request.POST,
        instance=approval,
        initial={
            "visualisation": application_template,
            "approver": request.user,
            "approved": False,
        },
    )
    if form.is_valid():
        form.save()
        return redirect(request.path)

    form_errors = [
        (field.id_for_label, field.errors[0]) for field in form if field.errors
    ]

    return _render_visualisation(
        request,
        'visualisation_approvals.html',
        gitlab_project,
        application_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='approvals',
        template_specific_context={"form": form, "form_errors": form_errors},
        status=400 if form_errors else 200,
    )


def visualisation_datasets_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_datasets_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_datasets_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def visualisation_datasets_html_GET(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    datasets = _datasets(request.user, application_template)

    return _render_visualisation(
        request,
        'visualisation_datasets.html',
        gitlab_project,
        application_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='datasets',
        template_specific_context={'datasets': datasets},
        status=200,
    )


def visualisation_datasets_html_POST(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    datasets = _datasets(request.user, application_template)

    # Sets for O(1) lookup, and lists for deterministic looping

    previously_selected_dataset_ids = [
        str(dataset['id']) for dataset, _ in datasets if dataset['selected']
    ]
    previously_selected_dataset_ids_set = set(previously_selected_dataset_ids)
    selectable_dataset_ids_set = {
        str(dataset['id']) for dataset, _ in datasets if dataset['selectable']
    }

    selected_dataset_ids = request.POST.getlist('dataset')
    selected_dataset_ids_set = set(selected_dataset_ids)

    datasets_ids_to_give_access_to = [
        dataset_id
        for dataset_id in selected_dataset_ids
        if dataset_id in selectable_dataset_ids_set
        and dataset_id not in previously_selected_dataset_ids_set
    ]
    datasets_ids_to_remove_access_from = [
        dataset_id
        for dataset_id in previously_selected_dataset_ids
        if dataset_id in selectable_dataset_ids_set
        and dataset_id not in selected_dataset_ids_set
    ]

    visualisation_template_content_type_id = ContentType.objects.get_for_model(
        VisualisationTemplate, for_concrete_model=False
    ).pk
    dataset_content_type_id = ContentType.objects.get_for_model(
        MasterDataset, for_concrete_model=False
    ).pk

    # We are happy with parallel requests modifying permissions without error,
    # so we eat IntegrityError and DoesNotExist.
    #
    # We can also assume every dataset is a DataSet and not a ReferenceDataset,
    # since ReferenceDatasets are not selectable

    for dataset_id in datasets_ids_to_give_access_to:
        dataset = MasterDataset.objects.get(id=dataset_id)

        try:
            with transaction.atomic():
                DataSetApplicationTemplatePermission.objects.create(
                    dataset=dataset, application_template=application_template
                )
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=visualisation_template_content_type_id,
                    object_id=application_template.id,
                    object_repr=force_str(application_template),
                    action_flag=CHANGE,
                    change_message=f'Gave access to dataset {dataset} '
                    f'({dataset.id}) using the visualisation UI',
                )
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=dataset_content_type_id,
                    object_id=dataset.id,
                    object_repr=force_str(dataset),
                    action_flag=CHANGE,
                    change_message=f'Gave access from {application_template} '
                    f'({application_template.id}) using the visualisation UI',
                )
        except IntegrityError:
            pass

    for dataset_id in datasets_ids_to_remove_access_from:
        dataset = MasterDataset.objects.get(id=dataset_id)

        try:
            with transaction.atomic():
                DataSetApplicationTemplatePermission.objects.get(
                    dataset=dataset, application_template=application_template
                ).delete()
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=visualisation_template_content_type_id,
                    object_id=application_template.id,
                    object_repr=force_str(application_template),
                    action_flag=CHANGE,
                    change_message=f'Removed access to the dataset {dataset} '
                    f'({dataset.id}) using the visualisation UI',
                )
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=dataset_content_type_id,
                    object_id=dataset.id,
                    object_repr=force_str(dataset),
                    action_flag=CHANGE,
                    change_message=f'Removed access from {application_template} '
                    f'({application_template.id}) using the visualisation UI',
                )
        except DataSetApplicationTemplatePermission.DoesNotExist:
            pass

    messages.success(request, 'Saved datasets access')

    return redirect('visualisations:datasets', gitlab_project_id=gitlab_project['id'])


def _datasets(user, application_template):
    # The interface must:
    # - show the datasets that the application already has access to,
    # - show the datasets that the user has access to,
    # - not duplicate datasets that are both of the above, and
    # - allow selection or unselection of only the datasets the user has
    #   access to that are also REQUIRES_AUTHORIZATION.
    # This means the user won't be able to unselect datasets that the
    # application already has access to, but the users doesn't. This is
    # deliberate: if they could unselect such datasets, they wouldn't be able
    # to reverse the change, which may need urgent contact with support to
    # restore access

    source_tables_user = source_tables_for_user(user)
    source_tables_app = source_tables_for_app(application_template)

    selectable_dataset_ids = set(
        source_table['dataset']['id']
        for source_table in source_tables_user
        if source_table['dataset']['user_access_type'] == 'REQUIRES_AUTHORIZATION'
    )

    selected_dataset_ids = set(
        source_table['dataset']['id'] for source_table in source_tables_app
    )

    source_tables_without_select_info = _without_duplicates_preserve_order(
        source_tables_user + source_tables_app,
        key=lambda x: (x['dataset']['id'], x['schema'], x['table']),
    )

    source_tables = [
        {
            'dataset': {
                'selectable': source_table['dataset']['id'] in selectable_dataset_ids,
                'selected': source_table['dataset']['id'] in selected_dataset_ids,
                **source_table['dataset'],
            },
            **{key: value for key, value in source_table.items() if key != 'dataset'},
        }
        for source_table in source_tables_without_select_info
    ]

    tables_sorted_by_dataset = sorted(
        source_tables,
        key=lambda x: (
            x['dataset']['name'],
            x['dataset']['id'],
            x['schema'],
            x['table'],
        ),
    )

    return [
        (dataset, list(tables))
        for dataset, tables in itertools.groupby(
            tables_sorted_by_dataset, lambda x: x['dataset']
        )
    ]


def visualisation_publish_html_view(request, gitlab_project_id):
    if not request.user.has_perm('applications.develop_visualisations'):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)

    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    if request.method == 'GET':
        return visualisation_publish_html_GET(request, gitlab_project)

    if request.method == 'POST':
        return visualisation_publish_html_POST(request, gitlab_project)

    return HttpResponse(status=405)


def _visualisation_is_approved(application_template):
    return (
        VisualisationApproval.objects.filter(
            visualisation=application_template, approved=True
        ).count()
        >= 2
    )


def _visualisation_is_published(application_template):
    return application_template.visible


def _visualisation_catalogue_item_is_complete(catalogue_item):
    return all(
        [
            catalogue_item.visualisation_template,
            catalogue_item.name,
            catalogue_item.slug,
            catalogue_item.short_description,
            catalogue_item.description,
            catalogue_item.enquiries_contact,
            catalogue_item.secondary_enquiries_contact,
            catalogue_item.information_asset_owner,
            catalogue_item.information_asset_manager,
            catalogue_item.licence,
            catalogue_item.retention_policy,
            catalogue_item.restrictions_on_usage,
            catalogue_item.personal_data,
        ]
    )


def _render_visualisation_publish_html(
    request, gitlab_project, catalogue_item=None, errors=None
):
    if not catalogue_item:
        catalogue_item = _get_visualisation_catalogue_item_for_gitlab_project(
            gitlab_project
        )
    application_template = catalogue_item.visualisation_template
    visualisation_approved = _visualisation_is_approved(application_template)
    visualisation_published = _visualisation_is_published(application_template)
    visualisation_domain = (
        f"{application_template.host_basename}.{settings.APPLICATION_ROOT_DOMAIN}"
    )
    catalogue_item_complete = _visualisation_catalogue_item_is_complete(catalogue_item)
    return _render_visualisation(
        request,
        'visualisation_publish.html',
        gitlab_project,
        application_template,
        _visualisation_branches(gitlab_project),
        current_menu_item='publish',
        template_specific_context={
            'visualisation_domain': visualisation_domain,
            'visualisation_link': f"{request.scheme}://{visualisation_domain}",
            "catalogue_complete": catalogue_item_complete,
            "catalogue_published": catalogue_item.published,
            "visualisation_published": visualisation_published,
            "approved": visualisation_approved,
            "errors": errors,
        },
    )


def visualisation_publish_html_GET(request, gitlab_project):
    return _render_visualisation_publish_html(request, gitlab_project)


@transaction.atomic
def _set_published_on_catalogue_item(request, gitlab_project, catalogue_item, publish):
    visualisation_approved = _visualisation_is_approved(
        catalogue_item.visualisation_template
    )
    visualisation_published = _visualisation_is_published(
        catalogue_item.visualisation_template
    )
    catalogue_item_complete = _visualisation_catalogue_item_is_complete(catalogue_item)
    if publish is False or (
        visualisation_approved and visualisation_published and catalogue_item_complete
    ):
        catalogue_item.published = publish
        catalogue_item.save()

        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(get_user_model()).pk,
            object_id=catalogue_item.pk,
            object_repr=force_str(catalogue_item),
            action_flag=CHANGE,
            change_message=f"Published {catalogue_item}"
            if publish
            else f"Unpublished {catalogue_item}",
        )

        return redirect(request.path)

    if visualisation_approved is False:
        error = (
            reverse("visualisations:approvals", args=(gitlab_project['id'],)),
            "The visualisation must be approved by two developers before it can be published.",
        )

    elif visualisation_published is False:
        error = (
            request.path,
            "The visualisation must be published before you can add it to the catalogue.",
        )

    elif catalogue_item_complete is False:
        error = (
            reverse("visualisations:catalogue-item", args=(gitlab_project['id'],)),
            "You must complete all fields of the catalogue item before it can be published.",
        )

    else:
        raise Exception("Cannot publish to catalogue - not sure why")

    return _render_visualisation_publish_html(
        request, gitlab_project, catalogue_item=catalogue_item, errors=[error]
    )


@transaction.atomic
def _set_published_on_visualisation(
    request, gitlab_project, application_template, publish
):
    visualisation_approved = _visualisation_is_approved(application_template)
    if publish is False or visualisation_approved:
        application_template.visible = publish
        application_template.save()

        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(get_user_model()).pk,
            object_id=application_template.pk,
            object_repr=force_str(application_template),
            action_flag=CHANGE,
            change_message=f"Published {application_template}"
            if publish
            else f"Unpublished {application_template}",
        )

        return redirect(request.path)

    if visualisation_approved is False:
        error = (
            reverse("visualisations:approvals", args=(gitlab_project['id'],)),
            "The visualisation must be approved by two developers before it can be published.",
        )

    else:
        raise Exception("Cannot publish visualisation - not sure why")

    return _render_visualisation_publish_html(request, gitlab_project, errors=[error])


def visualisation_publish_html_POST(request, gitlab_project):
    application_template = _application_template(gitlab_project)
    action = request.POST.get('action', '').lower()
    catalogue_item = _get_visualisation_catalogue_item_for_gitlab_project(
        gitlab_project
    )

    if action == 'publish-catalogue':
        return _set_published_on_catalogue_item(
            request, gitlab_project, catalogue_item, publish=True
        )

    elif action == 'unpublish-catalogue':
        return _set_published_on_catalogue_item(
            request, gitlab_project, catalogue_item, publish=False
        )

    elif action == 'publish-visualisation':
        return _set_published_on_visualisation(
            request, gitlab_project, application_template, publish=True
        )

    elif action == 'unpublish-visualisation':
        return _set_published_on_visualisation(
            request, gitlab_project, application_template, publish=False
        )

    return HttpResponse(
        status=400,
        content=(
            f'Invalid action: {action} is not one of '
            '[publish-catalogue|unpublish-catalogue|publish-visualisation]'.encode(
                'utf8'
            )
        ),
        content_type='utf8',
    )


def _without_duplicates_preserve_order(seq, key):
    # Based on https://stackoverflow.com/a/480227/1319998, but with a key to
    # base uniqueness on
    seen = set()
    return [x for x in seq if not (key(x) in seen or seen.add(key(x)))]


class UserToolSizeConfigurationView(SuccessMessageMixin, UpdateView):

    model = UserToolConfiguration
    fields = ['size']
    template_name = 'user_tool_size_configuration_form.html'
    success_message = "Saved %(tool_template)s size"

    def get_object(self, queryset=None):
        try:
            return UserToolConfiguration.objects.get(
                user=self.request.user,
                tool_template__host_basename=self.kwargs['tool_host_basename'],
            )
        except UserToolConfiguration.DoesNotExist:
            try:
                return UserToolConfiguration(
                    user=self.request.user,
                    tool_template=ToolTemplate.objects.get(
                        host_basename=self.kwargs['tool_host_basename']
                    ),
                )
            except ToolTemplate.DoesNotExist:
                raise Http404

    def get_success_url(self):
        return reverse('applications:tools')

    def get_success_message(self, cleaned_data):
        return self.success_message % dict(tool_template=self.object.tool_template,)


def _download_log(filename, events):
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename={filename}.log'
    with closing(StringIO()) as logfile:
        if events:
            for event in events:
                logfile.write(
                    f'{datetime.datetime.fromtimestamp(event["timestamp"] / 1000)} - {event["message"]}\n'
                )
        else:
            logfile.write('No logs were found for this visualisation.')
        response.write(logfile.getvalue())
    return response


def visualisation_latest_log_GET(request, gitlab_project_id, commit_id):
    if not gitlab_has_developer_access(request.user, gitlab_project_id):
        raise PermissionDenied()

    gitlab_project = _visualisation_gitlab_project(gitlab_project_id)
    application_template = _application_template(gitlab_project)
    filename = f'{gitlab_project["name"]}-{commit_id}.log'

    try:
        app_instance = ApplicationInstance.objects.filter(
            application_template=application_template, commit_id=commit_id
        ).latest('created_date')
    except ApplicationInstance.DoesNotExist:
        return _download_log(filename, [])

    container_name = json.loads(app_instance.spawner_application_template_options)[
        'CONTAINER_NAME'
    ]
    task_arn = json.loads(app_instance.spawner_application_instance_id)[
        'task_arn'
    ].split('/')[-1]

    log_stream = f'{container_name}/{container_name}/{task_arn}'

    return _download_log(
        filename,
        fetch_visualisation_log_events(
            settings.VISUALISATION_CLOUDWATCH_LOG_GROUP, log_stream
        ),
    )
