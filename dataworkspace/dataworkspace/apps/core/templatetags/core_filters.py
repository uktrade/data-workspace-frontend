from django import template
from django.forms import ChoiceField, Field

register = template.Library()


@register.filter
def is_choice_field(field: Field):
    return isinstance(field, ChoiceField)


@register.filter
def get_choice_field_data_for_gtm(field: ChoiceField):
    """
    Takes a Django form ChoiceField and returns a string where selected options are concatenated
    and separated by semi-colons - as wanted by performance analysts.

    This is intended to be used to pass filters into Google Tag Manager's Data Layer as JSON for
    analytics.
    """
    return ';'.join(sorted(x.data['label'] for x in field if x.data['selected']))
