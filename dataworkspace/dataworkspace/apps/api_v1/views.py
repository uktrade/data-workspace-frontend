import json

import boto3

from django.http import JsonResponse

from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationTemplate
from dataworkspace.apps.applications.spawner import spawn
from dataworkspace.apps.applications.utils import (
    api_application_dict,
    application_api_is_allowed,
    application_template_and_data_from_host,
    get_api_visible_application_instance_by_public_host,
    set_application_stopped,
)
from dataworkspace.apps.core.utils import (
    create_s3_role,
    new_private_database_credentials,
)


def applications_api_view(request):
    return \
        applications_api_GET(request) if request.method == 'GET' else \
        JsonResponse({}, status=405)


def applications_api_GET(request):
    return JsonResponse({
        'applications': [
            api_application_dict(application)
            for application in ApplicationInstance.objects.filter(
                state__in=['RUNNING', 'SPAWNING'],
            )
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

    try:
        application_template, public_host_data = application_template_and_data_from_host(public_host)
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
        request.user.email, str(request.user.profile.sso_id), public_host_data,
        application_instance.id, application_template.spawner_options, credentials,
        request.GET.get('__cpu', None), request.GET.get('__memory', None),
    )

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
    application_instance.save(update_fields=['state'])

    return JsonResponse({}, status=200)


def application_api_DELETE(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=200)

    set_application_stopped(application_instance)

    return JsonResponse({}, status=200)


def aws_credentials_api_view(request):
    return \
        aws_credentials_api_GET(request) if request.method == 'GET' else \
        JsonResponse({}, status=405)


def aws_credentials_api_GET(request):
    client = boto3.client('sts')
    role_arn, _ = create_s3_role(request.user.email, str(request.user.profile.sso_id))

    # Creating new credentials unfortunately sometimes fails
    max_attempts = 3
    for i in range(0, 3):
        try:
            credentials = client.assume_role(
                RoleArn=role_arn,
                RoleSessionName='s3_access_' + str(request.user.profile.sso_id),
                DurationSeconds=60 * 60,
            )['Credentials']
        except Exception:
            if i == max_attempts - 1:
                raise
        else:
            break

    return JsonResponse({
        'AccessKeyId': credentials['AccessKeyId'],
        'SecretAccessKey': credentials['SecretAccessKey'],
        'SessionToken': credentials['SessionToken'],
        'Expiration': credentials['Expiration']
    }, status=200)
