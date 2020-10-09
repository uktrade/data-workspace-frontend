from urllib import parse

from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):

    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        query[key] = value

    return f"{context['request'].build_absolute_uri('?')}?{query.urlencode()}"


@register.filter
def quote_plus(data):
    return parse.quote_plus(data)
