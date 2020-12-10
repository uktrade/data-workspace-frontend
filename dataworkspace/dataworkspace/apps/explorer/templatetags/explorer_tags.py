from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def format_duration(milli_seconds, short=False):
    q, r = divmod(milli_seconds, 1000)
    millis = round(r, 2)
    seconds = int(q % 60)
    minutes = int((q // 60) % 60)
    hours = int(q // 3600)

    if short:
        hour_unit = 'h'
        minute_unit = 'm'
        second_unit = 's'
        millis_unit = 'ms'
    else:
        hour_unit = f' hour{"s" if hours != 1 else ""}'
        minute_unit = f' minute{"s" if minutes != 1 else ""}'
        second_unit = f' second{"s" if seconds != 1 else ""}'
        millis_unit = f' millisecond{"s" if millis != 1 else ""}'

    if hours:
        return f'{hours}{hour_unit} {minutes}{minute_unit} ' f'{seconds}{second_unit}'
    elif minutes:
        return f'{minutes}{minute_unit} {seconds}{second_unit}'
    elif seconds:
        millis = int(r)
        return f'{seconds}{second_unit} {millis}{millis_unit}'
    return f'{millis}{millis_unit}'


@register.filter
def format_duration_short(milli_seconds):
    return format_duration(milli_seconds, short=True)
