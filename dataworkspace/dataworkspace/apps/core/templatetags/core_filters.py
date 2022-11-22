import bleach
from bs4 import BeautifulSoup

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


def _filter_language_classes(_, name, value):
    return name == "class" and value in [
        "language-python",
        "language-r",
        "language-json",
        "language-bash",
        "language-pgsql",
    ]


@register.filter
def minimal_markup(text):
    return mark_safe(
        bleach.clean(
            text or "",
            tags=[
                "div",
                "em",
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
                "a",
                "pre",
                "code",
            ],
            attributes={"a": ["href", "title"], "code": _filter_language_classes},
            strip=True,
        )
    )


@register.filter
def design_system_rich_text(text):
    """
    Add govuk design system classes to cleaned rich text
    """
    class_map = {
        "p": "govuk-body",
        "a": "govuk-link",
        "h3": "govuk-heading-l",
        "h4": "govuk-heading-m",
        "h5": "govuk-heading-s",
        "h6": "govuk-heading-xs",
        "ul": "govuk-list govuk-list--bullet",
        "ol": "govuk-list govuk-list--number",
    }
    soup = BeautifulSoup(minimal_markup(text), "html.parser")
    for tag_name, class_name in class_map.items():
        for el in soup.find_all(tag_name):
            el["class"] = el.get("class", []) + class_name.split(" ")
    return mark_safe(str(soup))


@register.filter("startswith")
def startswith(text, starts):
    if isinstance(text, str):
        return text.startswith(starts)

    return False
