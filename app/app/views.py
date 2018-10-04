from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)


def healthcheck_view(_):
    return HttpResponse('OK')


def credentials_view(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed()

    if 'email_address' not in request.POST:
        return HttpResponseBadRequest()

    return JsonResponse({
    })
