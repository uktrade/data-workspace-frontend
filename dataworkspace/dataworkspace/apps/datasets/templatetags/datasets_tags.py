import json

from datetime import datetime
from typing import Optional
from urllib import parse

from dateutil import parser
from dateutil.relativedelta import relativedelta
import pytz

from django import template
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.safestring import mark_safe
from escapejson import escapejson

register = template.Library()


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
    return parser.parse(date_string)


@register.filter
def can_edit_dataset(user, dataset):
    return (
        user == dataset.information_asset_owner
        or user == dataset.information_asset_manager
        or user.is_superuser
        or (
            hasattr(dataset, "data_catalogue_editors")
            and user in dataset.data_catalogue_editors.all()
        )
    )


@register.filter
def can_manage_editors(user, model):
    return (
        user.is_superuser
        or user == model.information_asset_owner
        or user == model.information_asset_manager
    )


@register.filter
def can_manage_data(user, model):
    return (
        user.is_superuser
        or user == model.information_asset_owner
        or user == model.information_asset_manager
        or user in model.data_catalogue_editors.all()
    )


@register.filter
def to_json(data):
    def handler(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()

        return str(obj)

    return mark_safe(escapejson(json.dumps(data, default=handler)))


@register.filter
def sensitivity_with_descriptor(value):
    sensitivity_with_descriptor_dict = {
        "PERSONAL": "PERSONAL (relates to an identifiable person)",
        "COMMERCIAL": "COMMERCIAL (contains market-sensitive information)",
        "LOCSEN": "LOCSEN (sensitive information that locally-engaged staff overseas must not access)",
    }

    return sensitivity_with_descriptor_dict[str(value)]


@register.simple_tag
def saved_grid_config(user, source):
    # pylint: disable=import-outside-toplevel
    from dataworkspace.apps.accounts.models import UserDataTableView

    try:
        return UserDataTableView.objects.get(
            user=user,
            source_object_id=str(source.id),
            source_content_type=ContentType.objects.get_for_model(source),
        ).grid_config()
    except UserDataTableView.DoesNotExist:
        return {}


@register.filter
def timedelta_to_minutes(td):
    return round(td.total_seconds() / 60, 2)


@register.filter
def format_table_name(table_name):
    return table_name.replace("_", " ")
