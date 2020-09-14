from django import template

from dataworkspace.apps.datasets.model_utils import (
    get_linked_field_identifier_name,
    get_linked_field_display_fields,
)


register = template.Library()


@register.simple_tag
def linked_field_identifier_name(field):
    return get_linked_field_identifier_name(field)


@register.simple_tag
def linked_field_display_field_names(field):
    return get_linked_field_display_fields(field)


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):

    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        query[key] = value

    return f"{context['request'].build_absolute_uri('?')}?{query.urlencode()}"
