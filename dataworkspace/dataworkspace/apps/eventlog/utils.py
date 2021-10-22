from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http.request import HttpRequest
from django.utils.encoding import force_text

from dataworkspace.apps.eventlog.models import EventLog


def log_event(request, event_type, related_object=None, extra=None):
    user = request.user
    if 'impersonated_user' in request.session:
        from dataworkspace.apps.applications.utils import (  # pylint: disable=import-outside-toplevel
            get_sso_user,
        )

        user = get_sso_user(request)

    return EventLog.objects.create(
        user=user,
        event_type=event_type,
        related_object=related_object,
        extra=extra,
        impersonated_user=request.session.get('impersonated_user', None),
    )


def log_permission_change(
    request: HttpRequest, obj: models.Model, event_type: int, extra: dict, message: str
):
    """
    Log permission chagne dto both the django user history and to our custom event log.
    :param user: Admin user making permission change
    :param obj: The model the permission relates to
    :param event_type: The `EventLog` event type
    :param extra: Any extra data to be store against the `EventLog` record
    :param message: Message text for the django `LogEntry`
    :return:
    """
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=obj.id,
        object_repr=force_text(obj),
        action_flag=CHANGE,
        change_message=message,
    )
    extra.update({'message': message})
    log_event(request, event_type, related_object=obj, extra=extra)
