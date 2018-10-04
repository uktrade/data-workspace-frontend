from django.http import HttpResponse


def healthcheck_view(_):
    return HttpResponse('OK')
