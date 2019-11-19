from django import template

from dataworkspace.apps.datasets.model_utils import (
    get_linked_field_identifier_name,
    get_linked_field_display_name,
)


register = template.Library()


@register.simple_tag
def linked_field_identifier_name(field):
    return get_linked_field_identifier_name(field)


@register.simple_tag
def linked_field_display_name(field):
    return get_linked_field_display_name(field)
