from datetime import datetime
from typing import Optional
from urllib import parse
from dateutil.relativedelta import relativedelta
import pytz

from django import template
from django.utils import timezone


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


@register.filter
def date_with_gmt_offset(utc_date: Optional[datetime]) -> Optional[str]:
    """
    Given a UTC date return a pretty representation with GMT offset.

    E.g.

    2020-01-01 11:40 ->	Jan 1, 2020, 11:40am, GMT
    2020-07-16 11:40 ->	Jul 16, 2020, 12:40pm, GMT+1
    """
    if not utc_date:
        return None

    if timezone.is_naive(utc_date):
        utc_date = utc_date.replace(tzinfo=pytz.UTC)

    timezone.activate(pytz.timezone('Europe/London'))
    localised_date = timezone.localtime(utc_date)
    offset = relativedelta(
        localised_date.replace(tzinfo=None), utc_date.replace(tzinfo=None)
    )
    return localised_date.strftime(
        f'%b %-d, %Y, %-I:%M%P, GMT{(f"+{offset.hours}" if offset.hours else "")}'
    )
