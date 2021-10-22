from functools import wraps

from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event


def log_user_impersonation(func):
    """
    Log urls hit while a user is impersonating another user.
    """

    @wraps(func)
    def log_impersonation(request, *args, **kwargs):
        if 'impersonated_user' in request.session:
            log_event(
                request,
                EventLog.TYPE_IMPERSONATED_PAGE_VIEW,
                extra={
                    'method': request.method,
                    'url': request.build_absolute_uri(),
                    'data': request.POST.dict()
                    if request.method == 'POST'
                    else request.GET.dict(),
                },
            )
        return func(request, *args, **kwargs)

    return log_impersonation
