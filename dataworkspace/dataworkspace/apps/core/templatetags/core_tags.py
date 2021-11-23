import json
import re

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def get_attr(model, field):
    """Gets an attribute of an object dynamically from a string name"""
    return getattr(model, str(field), None)


@register.filter
def get_key(dictionary, field):
    """Gets an key of an dictionary dynamically from a name"""
    return dictionary[field]


@register.filter
def zero_width_space_after(string, sub):
    zero_width_space = "\u200B"
    return string.replace(sub, f"{sub}{zero_width_space}")


@register.filter
def add_class(field, class_attr):
    if "class" in field.field.widget.attrs:
        field.field.widget.attrs["class"] = "{} {}".format(
            field.field.widget.attrs["class"], class_attr
        )
    else:
        field.field.widget.attrs["class"] = class_attr
    return field


@register.filter
def add_field_error(field):
    return add_class(field, "{}--error".format(field.field.widget.attrs.get("class")))


@register.filter
def pretty_json(field):
    return format_html("<pre>{0}</pre>", json.dumps(field, indent=2))


@register.filter
def not_set_if_none(value):
    if value in ["", None]:
        return format_html('<span class="unknown">Not set</span>')
    return value


@register.filter
def spawner_memory(value):
    return "-" if not value else str(int(value) / 1024).rstrip("0").rstrip(".") + "GB"


@register.filter
def spawner_cpu(value):
    return "-" if not value else str(int(value) / 1024).rstrip("0").rstrip(".")


@register.simple_tag(takes_context=True)
def browser_is_internet_explorer(context, **kwargs):
    user_agent = context["request"].META.get("HTTP_USER_AGENT", "")
    return re.search(r"MSIE|Trident/7\.0; rv:\d+", user_agent) is not None
