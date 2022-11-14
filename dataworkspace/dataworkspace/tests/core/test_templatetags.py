from django.forms import Form, ChoiceField, MultipleChoiceField
import pytest

from dataworkspace.apps.core.templatetags.core_filters import (
    get_choice_field_data_for_gtm,
    minimal_markup,
)


class _ExampleForm(Form):
    single = ChoiceField(choices=((1, "one"), (2, "two"), (3, "three")), required=False)
    multi = MultipleChoiceField(
        choices=((1, "one"), (2, "two"), (3, "three"), (4, "four"), (5, "five")),
        required=False,
    )


@pytest.mark.parametrize("selections, expected_string", (([], ""), ([1], "one"), ([3], "three")))
def test_get_single_choice_field_data_for_gtm(selections, expected_string):
    form = _ExampleForm(data={"single": selections})

    assert get_choice_field_data_for_gtm(form["single"]) == expected_string


@pytest.mark.parametrize(
    "selections, expected_string",
    (([], ""), ([1, 3], "one;three"), ([1, 3, 5], "five;one;three")),
)
def test_get_multi_choice_field_data_for_gtm(selections, expected_string):
    form = _ExampleForm(data={"multi": selections})

    assert get_choice_field_data_for_gtm(form["multi"]) == expected_string


@pytest.mark.parametrize(
    "input_, expected_output, error_message",
    (
        ("<div>test</div>", "<div>test</div>", "Allow divs in output"),
        ("<script>alert()</script>", "alert()", "Disallow script tags"),
        (
            '<a href="#" onclick="doSomething()">test</a>',
            '<a href="#">test</a>',
            "Disallow on click attributes",
        ),
    ),
)
def test_minimal_markup(input_, expected_output, error_message):
    assert minimal_markup(input_) == expected_output, error_message
