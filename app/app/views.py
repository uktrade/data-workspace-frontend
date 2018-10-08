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
    PublicDatabase,
)


def healthcheck_view(_):
    return HttpResponse('OK')


def databases_view(request):
    if 'HTTP_AUTHORIZATION' not in request.META:
        return HttpResponseBadRequest(json.dumps({'detail': 'The Authorization header must be set.'}))

    me_response = requests.get(settings.AUTHBROKER_URL + 'api/v1/user/me/', headers={
        'Authorization': request.META['HTTP_AUTHORIZATION'],
    })
    if me_response.status_code != 200:
        return HttpResponse(me_response.text, status=me_response.status_code)

    return JsonResponse({
        'databases': [{
            'id': database.id,
            'memorable_name': database.memorable_name,
            'db_name': database.db_name,
            'db_host': database.db_host,
            'db_port': database.db_port,
            'db_user': database.db_user,
            'db_password': database.db_password,
        } for database in PublicDatabase.objects.all().order_by(
            'memorable_name', 'created_date', 'id',
        )]
    }) if request.method == 'GET' else HttpResponseNotAllowed()


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401
