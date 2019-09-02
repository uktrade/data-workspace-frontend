import json

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def get_attr(model, field):
    """Gets an attribute of an object dynamically from a string name"""
    return getattr(model, str(field), None)


@register.filter
def add_class(field, class_attr):
    if 'class' in field.field.widget.attrs:
        field.field.widget.attrs['class'] = '{} {}'.format(
            field.field.widget.attrs['class'],
            class_attr
        )
    else:
        field.field.widget.attrs['class'] = class_attr
    return field


@register.filter
def add_field_error(field):
    return add_class(field, '{}--error'.format(
        field.field.widget.attrs.get('class')
    ))


@register.filter
def pretty_json(field):
    return format_html(
        '<pre>{0}</pre>',
        json.dumps(field, indent=2)
    )
