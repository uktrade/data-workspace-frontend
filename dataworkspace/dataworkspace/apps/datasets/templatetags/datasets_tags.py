from datetime import datetime
from typing import Optional
from urllib import parse
from dateutil.relativedelta import relativedelta
import pytz

from django import template
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag()
def visualisation_link_or_plain_text(text, condition, dataset_uuid, object_id):
    if condition:
        url = reverse("datasets:dataset_visualisation", args=[dataset_uuid, object_id])
        return mark_safe(f"<a class='govuk-link' href='{url}'>{text}</a>")

    return text


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):

    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value

    return f"{context['request'].build_absolute_uri('?')}?{query.urlencode()}"


@register.filter
def quote_plus(data):
    return parse.quote_plus(data)


def _get_localised_date(utc_date: datetime) -> datetime:
    if timezone.is_naive(utc_date):
        utc_date = utc_date.replace(tzinfo=pytz.UTC)

    timezone.activate(pytz.timezone("Europe/London"))
    localised_date = timezone.localtime(utc_date)
    offset = relativedelta(localised_date.replace(tzinfo=None), utc_date.replace(tzinfo=None))

    return localised_date, offset


@register.filter
def time_with_gmt_offset(utc_date: Optional[datetime]) -> Optional[str]:
    """
    See date_with_gmt_offset
    @param utc_date:
    @return:
    """
    if not utc_date:
        return None

    localised_date, offset = _get_localised_date(utc_date)
    return localised_date.strftime(f'%-I:%M%P, GMT{(f"+{offset.hours}" if offset.hours else "")}')


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

    localised_date, offset = _get_localised_date(utc_date)

    return localised_date.strftime(
        f'%-d %B %Y, %-I:%M%P, GMT{(f"+{offset.hours}" if offset.hours else "")}'
    )


@register.filter
def gmt_date(utc_date: Optional[datetime]) -> Optional[str]:
    if not utc_date:
        return None

    localised_date, _ = _get_localised_date(utc_date)
    return localised_date.strftime("%-d %B %Y")


@register.filter
def format_date_uk(date: Optional[datetime.date]) -> Optional[str]:
    if not date:
        return None

    return date.strftime("%-d %B %Y")


@register.filter
def parse_date_string(date_string: Optional[str]) -> Optional[str]:
    if date_string is None:
        return None
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")


@register.simple_tag()
def chart_link_or_plain_text(text, condition, dataset_uuid, object_id):
    if condition:
        url = reverse("datasets:dataset_chart", args=[dataset_uuid, object_id])
        return mark_safe(f"<a class='govuk-link' href='{url}'>{text}</a>")
    return text
