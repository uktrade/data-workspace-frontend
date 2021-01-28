from csp.decorators import csp_update
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

from dataworkspace.apps.core.utils import get_s3_prefix


def file_browser_html_view(request):
    return (
        file_browser_html_GET(request)
        if request.method == 'GET'
        else HttpResponse(status=405)
    )


@csp_update(
    CONNECT_SRC=[settings.APPLICATION_ROOT_DOMAIN, "https://s3.eu-west-2.amazonaws.com"]
)
def file_browser_html_GET(request):
    prefix = get_s3_prefix(str(request.user.profile.sso_id))

    return render(
        request,
        'files.html',
        {'prefix': prefix, 'bucket': settings.NOTEBOOKS_BUCKET},
        status=200,
    )
