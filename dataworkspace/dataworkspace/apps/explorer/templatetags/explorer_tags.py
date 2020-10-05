from django import template
from django.utils.module_loading import import_string

from dataworkspace.apps.explorer import app_settings


register = template.Library()


@register.inclusion_tag('explorer/export_buttons.html')
def export_buttons(query=None):
    exporters = []
    for name, classname in app_settings.EXPLORER_DATA_EXPORTERS:
        exporter_class = import_string(classname)
        exporters.append((name, exporter_class.name))
    return {
        'exporters': exporters,
        'query': query,
    }


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def format_duration(milli_seconds):
    q, r = divmod(milli_seconds, 1000)
    millis = round(r, 2)
    seconds = int(q % 60)
    minutes = int((q // 60) % 60)
    hours = int(q // 3600)

    hour_unit = f'hour{"s" if hours != 1 else ""}'
    minute_unit = f'minute{"s" if minutes != 1 else ""}'
    second_unit = f'second{"s" if seconds != 1 else ""}'
    millis_unit = f'millisecond{"s" if millis != 1 else ""}'

    if hours:
        return (
            f'{hours} {hour_unit} {minutes} {minute_unit} '
            f'{seconds} {second_unit} {millis} {millis_unit}'
        )
    elif minutes:
        return f'{minutes} {minute_unit} {seconds} {second_unit} {millis} {millis_unit}'
    elif seconds:
        return f'{seconds} {second_unit} {millis} {millis_unit}'
    return f'{millis} {millis_unit}'
