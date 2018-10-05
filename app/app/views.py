from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)

from app.models import (
    PublicDatabase,
)


def healthcheck_view(_):
    return HttpResponse('OK')


def databases_view(request):
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
