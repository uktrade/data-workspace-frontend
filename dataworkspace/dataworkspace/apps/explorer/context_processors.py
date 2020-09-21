from django.conf import settings


def expose_multiuser_setting(request):
    return {"MULTIUSER_DEPLOYMENT": settings.MULTIUSER_DEPLOYMENT}
