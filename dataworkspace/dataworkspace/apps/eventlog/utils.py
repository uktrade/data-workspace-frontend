from dataworkspace.apps.eventlog.models import EventLog


def log_event(user, event_type, related_object=None, extra=None):
    return EventLog.objects.create(
        user=user,
        event_type=event_type,
        related_object=related_object,
        extra=extra
    )
