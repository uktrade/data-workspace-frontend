import bleach
from django import template

from django.forms import ChoiceField, Field
from django.utils.safestring import mark_safe

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

    # NB: The str() *is* required here as the labels are overridden for scrolling_filter into
    # a SearchableChoice object
    return ";".join(sorted(str(x.data["label"]) for x in field if x.data["selected"]))


@register.filter
def minimal_markup(text):
    return mark_safe(
        bleach.clean(
            text or "",
            tags=[
                "div",
                "em",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "ul",
                "ol",
                "li",
                "strong",
                "br",
            ],
            attributes={},
            strip=True,
        )
    )


@register.filter("startswith")
def startswith(text, starts):
    if isinstance(text, str):
        return text.startswith(starts)

    return False
