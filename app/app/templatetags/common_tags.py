from django import template

register = template.Library()


@register.filter
def get_attr(model, field):
    return getattr(model, field)
