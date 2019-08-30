import json
import logging

from django.http import JsonResponse

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationTemplate
from dataworkspace.apps.applications.spawner import spawn
from dataworkspace.apps.applications.utils import (
    api_application_dict,
    application_api_is_allowed,
    application_template_and_data_from_host,
    get_api_visible_application_instance_by_public_host,
    set_application_stopped,
)
from dataworkspace.apps.core.utils import new_private_database_credentials
from dataworkspace.apps.ext_datasets.models import OMISDataset
from dataworkspace.apps.ext_datasets.serializers import OMISDatasetSerializer

logger = logging.getLogger('app')


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
        application_template, _ = application_template_and_data_from_host(public_host)
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
    application_instance.save(update_fields=['state'])

    return JsonResponse({}, status=200)


def application_api_DELETE(request, public_host):
    try:
        application_instance = get_api_visible_application_instance_by_public_host(public_host)
    except ApplicationInstance.DoesNotExist:
        return JsonResponse({}, status=200)

    set_application_stopped(application_instance)

    return JsonResponse({}, status=200)


class Echo:
    """An object that implements just the write method of the file-like
    interface.
    """

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class OMISDatasetViewSet(viewsets.GenericViewSet):
    """A viewset that provides `create-many` (which expects list of records),
    and `destroy-all` actions for OMISDataset.
    """
    serializer_class = OMISDatasetSerializer

    @action(detail=False, methods=['post'], url_path='create-many')
    def create_many(self, request, *args, **kwargs):
        """Creates multiple OMIS Dataset records.
        Expects list of dicts in the request data.
        """
        serializer = self.get_serializer(data=request.data['results'], many=True)
        if not serializer.is_valid():
            logger.debug('%s', serializer.errors)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        logger.info('Created OMISDataset record/s \n %s', serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'], url_path='destroy-all')
    def destroy_all(self, request):
        """Delete all records in OMISDataset table"""
        OMISDataset.objects.all().delete()
        logger.info('Deleted all records in OMISDataset model')
        return Response(status=status.HTTP_204_NO_CONTENT)
