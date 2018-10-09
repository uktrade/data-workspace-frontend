import json
from django.conf import (
    settings,
)
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    JsonResponse,
)
import requests

from app.models import (
    Database,
)


def healthcheck_view(_):
    return HttpResponse('OK')


def databases_view(request):
    response = \
        HttpResponseNotAllowed(['GET']) if request.method != 'GET' else \
        HttpResponseBadRequest(json.dumps({'detail': 'The Authorization header must be set.'})) if 'HTTP_AUTHORIZATION' not in request.META else \
        _databases(request.META['HTTP_AUTHORIZATION'])

    return response


def _databases(auth):
    me_response = requests.get(settings.AUTHBROKER_URL + 'api/v1/user/me/', headers={
        'Authorization': auth,
    })
    databases_reponse = \
        JsonResponse({'databases': _public_databases()}) if me_response.status_code == 200 else \
        HttpResponse(me_response.text, status=me_response.status_code)

    return databases_reponse


def _public_databases():
    return [{
        'id': database.id,
        'memorable_name': database.memorable_name,
        'db_name': settings.DATA_DB__[database.memorable_name]['NAME'],
        'db_host': settings.DATA_DB__[database.memorable_name]['HOST'],
        'db_port': int(settings.DATA_DB__[database.memorable_name]['PORT']),
        'db_user': settings.DATA_DB__[database.memorable_name]['USER'],
        'db_password': settings.DATA_DB__[database.memorable_name]['PASSWORD'],
    } for database in Database.objects.all().order_by(
        'memorable_name', 'created_date', 'id',
    )]


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401
