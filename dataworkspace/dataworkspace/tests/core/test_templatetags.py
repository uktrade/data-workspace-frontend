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
        ("foo", "<p>foo</p>", "Text should be wrapped in paragraph tags"),
        (
            "foo\nbar",
            "<p>foo\nbar</p>",
            "Single newlines should not create separate paragraphs",
        ),
        (
            "foo\n\nbar",
            "<p>foo</p>\n<p>bar</p>",
            "Double newlines should create new paragraphs",
        ),
        (
            "foo\n\n\n\nbar",
            "<p>foo</p>\n<p>bar</p>",
            "Redundant newlines should be ignored",
        ),
        (
            "* one\n* two",
            "<ul>\n<li>one</li>\n<li>two</li>\n</ul>",
            "Unordered lists should be rendered",
        ),
        (
            "1. one\n2. two",
            "<ol>\n<li>one</li>\n<li>two</li>\n</ol>",
            "Ordered lists should be rendered",
        ),
        ("[link](https://www.unsafe.evil)", "<p>link</p>", "Links are not allowed"),
        ("<script>alert(1);</script>", "alert(1);", "Script tags should be stripped"),
        ('<img src="foo"/>', "<p></p>", "Img tags should be stripped"),
        (
            "**some bold text**",
            "<p><strong>some bold text</strong></p>",
            "Surrounding with ** should create strong text",
        ),
        (
            "title  \nwith a line break",
            "<p>title<br>\nwith a line break</p>",
            "Ending a line with two spaces should insert a line break",
        ),
    ),
)
def test_minimal_markup(input_, expected_output, error_message):
    assert minimal_markup(input_) == expected_output, error_message
